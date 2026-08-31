import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from agents.tools import create_razorpay_order, check_payment_status
from services.payment_resolution import resolve_payment_status
from services.refund_service import initiate_refund, check_refund_status

# The application creates the FastAPI app dynamically, we will assume standard imports
# We use mock DB interactions for all testing since we are instructed to use mocks.

@pytest.fixture
def mock_supabase():
    with patch("utils.supabase_client.supabase") as mock_supa:
        yield mock_supa

@pytest.fixture
def mock_rzp():
    with patch("razorpay_service.client.rzp") as mock_rzp_client:
        yield mock_rzp_client
        
@pytest.fixture
def mock_orders():
    with patch("razorpay_service.orders.create_order") as mock_create_order:
        mock_create_order.return_value = {"id": "order_rzp_12345"}
        yield mock_create_order

def test_phase8_1_create_razorpay_order_fails_locally(mock_supabase, mock_orders):
    """Scenario 1 & 2: Razorpay succeeds but local insert fails. 
    It should NOT rollback the intent's razorpay_order_id.
    It should return a partial success message.
    """
    # Setup intent state
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "purchase_intent_id": "pi_123",
        "purchase_state": "USER_CONFIRMED",
        "user_confirmed": True,
        "amount_paise": 1000,
        "confirmed_amount_paise": 1000,
        "basket": [{"product_id": "p_1", "quantity": 1}],
        "confirmed_basket": [{"product_id": "p_1", "quantity": 1}],
        "conversation_id": "sess_1"
    }
    # Simulate DB update to ORDER_CREATING works
    mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{
        "purchase_intent_id": "pi_123",
        "basket": [{"product_id": "p_1", "quantity": 1}]
    }]
    
    # Simulate product check works
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "product_id": "p_1", "active": True, "inventory_qty": 10, "price_paise": 1000
    }
    
    # Simulate local mapping creation fails
    mock_supabase.table.return_value.insert.side_effect = Exception("DB Timeout")
    
    state = {"purchase_context": {"purchase_intent_id": "pi_123"}, "session_id": "sess_1"}
    result = create_razorpay_order(state)
    
    assert "System will recover automatically" in result
    
    # Assert we did NOT wipe razorpay_order_id 
    # Check update calls: first was ORDER_CREATING, second was PAYMENT_PENDING with razorpay_order_id
    update_calls = mock_supabase.table.return_value.update.call_args_list
    assert any("razorpay_order_id" in call[0][0] and call[0][0]["purchase_state"] == "PAYMENT_PENDING" for call in update_calls)
    
    # Check there is no rollback to USER_CONFIRMED where razorpay_order_id is None
    for call in update_calls:
        if "razorpay_order_id" in call[0][0]:
            assert call[0][0]["razorpay_order_id"] == "order_rzp_12345"

def test_phase8_4_retry_after_persistence_failure(mock_supabase, mock_orders):
    """Scenario 4: Retry after persistence failure recovers the order mapping."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "purchase_intent_id": "pi_123",
        "purchase_state": "PAYMENT_PENDING",
        "user_confirmed": True,
        "amount_paise": 1000,
        "razorpay_order_id": "order_rzp_12345", # Already exists
        "basket": [{"product_id": "p_1", "quantity": 1}],
        "conversation_id": "sess_1"
    }
    
    # Simulate local orders check: initially None, triggers _recover_local_order
    # the existing check for orders returns empty:
    mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = None
    
    state = {"purchase_context": {"purchase_intent_id": "pi_123"}, "session_id": "sess_1"}
    result = create_razorpay_order(state)
    
    assert "Razorpay Order already exists" in result
    
    # Ensure insert was called for recovery
    insert_calls = mock_supabase.table.return_value.insert.call_args_list
    assert any("order_id" in call[0][0] for call in insert_calls)
    assert any("synthetic_id" in call[0][0] and call[0][0]["entity_type"] == "order" for call in insert_calls)


def test_phase5_webhook_and_reconciliation_equivalence(mock_supabase):
    """Scenario 7, 10, 15: Webhook and reconciliation must produce same business result (Phase 5)."""
    # 1. Simulate webhook
    from services.payment_resolution import resolve_payment_status
    
    mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"synthetic_id": "ord_123"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "order_id": "ord_123", "purchase_intent_id": "pi_123"
    }
    
    intent_data_mock = {
        "purchase_intent_id": "pi_123", "purchase_state": "PAYMENT_PENDING", "amount_paise": 1000, "basket": []
    }
    # Second select for intent
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
        MagicMock(data={"order_id": "ord_123", "purchase_intent_id": "pi_123"}), # mapping -> order
        MagicMock(data=intent_data_mock) # order -> intent
    ]
    
    # Mock inventory RPC success
    mock_supabase.rpc.return_value.execute.return_value.data = {"status": "success"}
    
    res = resolve_payment_status("rzp_order_123", "rzp_pay_123", 1000, "CAPTURED", "webhook")
    assert res["status"] == "ok"
    assert res["state"] == "PAYMENT_SUCCESS"
    assert res["fulfillment"] == "FULFILLED"
    
    # RPC must be called
    mock_supabase.rpc.assert_called_once()
    
    # 2. Simulate reconciliation on same payment ID
    # Assume state is already PAYMENT_SUCCESS
    intent_data_mock["purchase_state"] = "PAYMENT_SUCCESS"
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
        MagicMock(data={"order_id": "ord_123", "purchase_intent_id": "pi_123"}),
        MagicMock(data=intent_data_mock)
    ]
    
    # Call should return terminal state
    res2 = resolve_payment_status("rzp_order_123", "rzp_pay_123", 1000, "CAPTURED", "reconciliation")
    assert res2["status"] == "ok"
    assert res2["reason"] == "terminal state"

def test_phase8_33_duplicate_refunds_prevented(mock_supabase, mock_rzp):
    """Scenario 31, 33: Concurrent refunds, Already refunded payment."""
    # Simulate DB unique constraint on insert
    mock_supabase.table.return_value.insert.side_effect = Exception("duplicate key value violates unique constraint uq_refund_idempotency")
    
    # Existing refund
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "status": "REFUNDED", "refund_id": "ref_123"
    }
    
    res = initiate_refund("pay_123", "rzp_pay_123", "ord_123", "cust_123", 1000)
    
    # It should not call Razorpay api
    mock_rzp.payment.refund.assert_not_called()
    assert res["status"] == "REFUNDED"
    assert res["refund_id"] == "ref_123"

def test_phase4_fulfillment_failure_triggers_refund(mock_supabase, mock_rzp):
    """Phase 4: When payment is captured but inventory cannot be fulfilled, refund workflow is triggered."""
    # Setup mapping
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
        MagicMock(data={"order_id": "ord_123", "purchase_intent_id": "pi_123"}),
        MagicMock(data={"purchase_intent_id": "pi_123", "purchase_state": "PAYMENT_PENDING", "amount_paise": 1000, "basket": []})
    ]
    
    # Mock inventory RPC failure (insufficient inventory)
    mock_supabase.rpc.return_value.execute.return_value.data = {"status": "insufficient_inventory"}
    
    # Mock rzp refund api
    mock_rzp.payment.refund.return_value = {"id": "rzp_ref_123"}
    
    res = resolve_payment_status("rzp_order_123", "rzp_pay_123", 1000, "CAPTURED")
    assert res["status"] == "ok"
    assert res["fulfillment"] == "UNFULFILLED"
    
    # Verify refund was inserted
    insert_calls = mock_supabase.table.return_value.insert.call_args_list
    assert any("refund_id" in call[0][0] and call[0][0]["status"] == "REFUND_PENDING" for call in insert_calls)
    
    # Verify Razorpay API was called
    mock_rzp.payment.refund.assert_called_once()
