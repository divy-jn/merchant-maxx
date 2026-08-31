import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from agents.tools import create_razorpay_order

@pytest.fixture
def mock_supabase():
    with patch("agents.tools.supabase") as mock_db, patch("services.payment_resolution.supabase", mock_db):
        yield mock_db

def _create_mock_intent(intent_id, overrides=None):
    base = {
        "purchase_intent_id": intent_id,
        "conversation_id": "conv_123",
        "customer_id": "cust_123",
        "purchase_state": "USER_CONFIRMED",
        "user_confirmed": True,
        "amount_paise": 100000, # 1000 INR
        "basket": [{"product_id": "prod_1", "quantity": 1}],
        "confirmed_basket": [{"product_id": "prod_1", "quantity": 1}],
        "confirmed_amount_paise": 100000
    }
    if overrides:
        base.update(overrides)
    return base

def _mock_db_responses(mock_supabase, intent, product_active=True, product_price=100000, product_qty=10, existing_orders=None, lock_data=None):
    # Mock intent fetch
    mock_intent_res = MagicMock()
    mock_intent_res.data = intent if intent else None
    
    # Mock atomic lock update
    mock_lock_res = MagicMock()
    mock_lock_res.data = lock_data if lock_data is not None else ([intent] if intent else [])
    
    # Mock product fetch
    mock_prod_res = MagicMock()
    mock_prod_res.data = {
        "product_id": "prod_1",
        "active": product_active,
        "price_paise": product_price,
        "inventory_qty": product_qty
    }
    
    # Mock existing orders
    mock_existing = MagicMock()
    mock_existing.data = existing_orders or []
    
    def side_effect(table_name):
        mock_table = MagicMock()
        if table_name == "purchase_intents":
            mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_intent_res
            mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_lock_res
        elif table_name == "products":
            mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_prod_res
        elif table_name == "orders":
            mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_existing
            mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_existing
        return mock_table
        
    mock_supabase.table.side_effect = side_effect
    return mock_supabase

def test_1_fake_user_confirmed(mock_supabase):
    """Test 1: LLM supplies fake user_confirmed state when DB says False"""
    intent = _create_mock_intent("pi_test", {"user_confirmed": False, "purchase_state": "PURCHASE_PENDING"})
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "explicit confirmation is required" in res

def test_2_fake_user_confirmed_state(mock_supabase):
    """Test 2: LLM supplies USER_CONFIRMED state when DB says otherwise"""
    intent = _create_mock_intent("pi_test", {"purchase_state": "PRODUCT_SELECTED"})
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "explicit confirmation is required" in res

def test_3_fake_basket(mock_supabase):
    """Test 3: LLM context supplies a modified basket that doesn't match confirmed"""
    # The vulnerability was the LLM changing the basket but keeping confirmation.
    # We simulate DB having a modified basket but the confirmed_basket is old.
    intent = _create_mock_intent("pi_test", {
        "basket": [{"product_id": "prod_1", "quantity": 2}],
        "confirmed_basket": [{"product_id": "prod_1", "quantity": 1}],
    })
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "basket has been modified since confirmation" in res

def test_4_fake_amount(mock_supabase):
    """Test 4: Amount mismatch"""
    intent = _create_mock_intent("pi_test", {
        "amount_paise": 50000,
        "confirmed_amount_paise": 100000,
    })
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "server-calculated amount does not match the confirmed amount" in res or "server-calculated basket total does not match purchase intent" in res

def test_5_legitimate_path(mock_supabase):
    """Test 5: Legitimate confirmed intent succeeds"""
    intent = _create_mock_intent("pi_test")
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    with patch("agents.tools.validate_action") as mock_validate:
        with patch("razorpay_service.orders.create_order", return_value={"id": "order_rzp_123"}):
            res = create_razorpay_order.invoke({"state": state})
            assert "Razorpay Order created successfully" in res
            mock_validate.assert_called_with("Closer", "create_razorpay_order",
                        {"purchase_intent_id": "pi_test", "user_confirmed": True,
                         "purchase_state": "USER_CONFIRMED", "entity_valid": True},
                        100000)

def test_6_already_successful_intent(mock_supabase):
    """Test 6: Intent is already PAYMENT_SUCCESS"""
    intent = _create_mock_intent("pi_test", {"purchase_state": "PAYMENT_SUCCESS", "razorpay_order_id": "order_rzp_999"})
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "already exists" in res

def test_7_failed_invalid_intent(mock_supabase):
    """Test 7: Intent is PAYMENT_FAILED"""
    intent = _create_mock_intent("pi_test", {"purchase_state": "PAYMENT_FAILED", "razorpay_order_id": "order_rzp_999"})
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    # Since Razorpay order ID exists, it returns idempotent response to check status,
    # or it will be blocked by explicit confirmation if we reset it.
    # In this case it has an order ID, so idempotency returns it.
    assert "already exists" in res

def test_8_basket_changed_after_confirmation(mock_supabase):
    """Test 8: Basket changed after confirmation (same as test 3)"""
    intent = _create_mock_intent("pi_test", {
        "basket": [{"product_id": "prod_1", "quantity": 1}, {"product_id": "prod_2", "quantity": 1}],
        "confirmed_basket": [{"product_id": "prod_1", "quantity": 1}]
    })
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "basket has been modified since confirmation" in res

def test_9_stale_confirmation(mock_supabase):
    """Test 9: Stale confirmation where confirmed_basket is null"""
    intent = _create_mock_intent("pi_test", {
        "confirmed_basket": None
    })
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "basket has been modified since confirmation" in res

def test_10_concurrent_payment_attempts(mock_supabase):
    """Test 10: Concurrent requests trying to lock"""
    intent = _create_mock_intent("pi_test")
    # Simulate that the update lock failed (returned 0 rows)
    _mock_db_responses(mock_supabase, intent, lock_data=[])
    
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    res = create_razorpay_order.invoke({"state": state})
    assert "intent state changed concurrently" in res

def test_11_cross_user_intent_idor(mock_supabase):
    """Test 11: One user's LLM attempts to use another user's intent"""
    intent = _create_mock_intent("pi_test")
    _mock_db_responses(mock_supabase, intent)
    # The state session_id belongs to a different user/conversation
    state = {"session_id": "conv_MALICIOUS", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    res = create_razorpay_order.invoke({"state": state})
    assert "ownership verification failed" in res

def test_12_direct_tool_invocation(mock_supabase):
    """Test 12: Direct tool invocation bypassing Closer"""
    # Even if Guardian/Closer is bypassed, the tool enforces DB state
    intent = _create_mock_intent("pi_test", {"user_confirmed": False, "purchase_state": "PURCHASE_PENDING"})
    _mock_db_responses(mock_supabase, intent)
    state = {"session_id": "conv_123", "purchase_context": {"purchase_intent_id": "pi_test"}}
    
    # Direct execution of the tool function logic
    res = create_razorpay_order.invoke({"state": state})
    assert "explicit confirmation is required" in res
