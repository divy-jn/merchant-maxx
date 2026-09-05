import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from agents.tools import create_razorpay_order

@pytest.fixture
def mock_supabase():
    with patch("agents.tools.supabase") as mock:
        yield mock

def test_create_razorpay_order_reuses_existing_order(mock_supabase):
    """Test that if a razorpay order already exists on the intent, it is reused."""
    state = {
        "session_id": "test_conv",
        "purchase_context": {"purchase_intent_id": "pi_123"}
    }

    # Mock intent fetch
    mock_intent_res = MagicMock()
    mock_intent_res.data = {
        "purchase_intent_id": "pi_123",
        "conversation_id": "test_conv",
        "razorpay_order_id": "order_existing123",
        "amount_paise": 50000,
        "customer_id": "cust_123",
        "basket": [{"product_id": "prod_1", "quantity": 1}]
    }
    mock_supabase.table().select().eq().maybe_single().execute.return_value = mock_intent_res

    # Mock local order missing
    mock_local_res = MagicMock()
    mock_local_res.data = None
    # We must patch the second select that checks for local orders

    def side_effect_table(table_name):
        mock_tbl = MagicMock()
        if table_name == "purchase_intents":
            mock_tbl.select().eq().maybe_single().execute.return_value = mock_intent_res
        elif table_name == "orders":
            mock_tbl.select().eq().limit().execute.return_value = mock_local_res
            mock_tbl.select().eq().maybe_single().execute.return_value = mock_local_res
        return mock_tbl

    mock_supabase.table.side_effect = side_effect_table

    with patch("agents.tools.logger") as mock_logger:
        with patch("services.payment_resolution._recover_local_order") as mock_recover:
            res = create_razorpay_order.invoke({"state": state})

            assert "Your order is already prepared." in res
            assert "order_existing123" not in res # Do not leak order ID
            assert "FATAL_ERROR" not in res
            # Verify recovery was called with the basket
            mock_recover.assert_called_once_with(
                "pi_123", "order_existing123", "cust_123", 50000,
                [{"product_id": "prod_1", "quantity": 1}], 0, 0, 0
            )

def test_create_razorpay_order_hides_fatal_error(mock_supabase):
    """Test that if local mapping fails, the customer sees a safe message, not FATAL_ERROR."""
    state = {
        "session_id": "test_conv",
        "purchase_context": {"purchase_intent_id": "pi_123"}
    }

    mock_intent_res = MagicMock()
    mock_intent_res.data = {
        "purchase_intent_id": "pi_123",
        "conversation_id": "test_conv",
        "purchase_state": "USER_CONFIRMED",
        "user_confirmed": True,
        "amount_paise": 50000,
        "confirmed_amount_paise": 50000,
        "customer_id": "cust_123",
        "basket": [{"product_id": "prod_1", "quantity": 1}],
        "confirmed_basket": [{"product_id": "prod_1", "quantity": 1}]
    }

    def side_effect_table(table_name):
        mock_tbl = MagicMock()
        if table_name == "purchase_intents":
            mock_tbl.select().eq().maybe_single().execute.return_value = mock_intent_res

            mock_update_res = MagicMock()
            mock_update_res.data = [mock_intent_res.data]
            mock_tbl.update().eq().eq().execute.return_value = mock_update_res

            mock_tbl.update().eq().execute.return_value = MagicMock() # for step 1 persistence
        elif table_name == "products":
            mock_prod = MagicMock()
            mock_prod.data = {"product_id": "prod_1", "active": True, "inventory_qty": 10, "price_paise": 50000}
            mock_tbl.select().eq().eq().maybe_single().execute.return_value = mock_prod
        elif table_name == "orders":
            mock_tbl.select().eq().limit().execute.return_value = MagicMock(data=[])

            # Make the insert throw an exception to simulate local mapping failure
            mock_tbl.insert().execute.side_effect = Exception("DB Timeout")
        return mock_tbl

    mock_supabase.table.side_effect = side_effect_table

    with patch("agents.tools.logger") as mock_logger:
        with patch("razorpay_service.orders.create_order", return_value={"id": "order_rzpnew"}):
            res = create_razorpay_order.invoke({"state": state})

            assert "We're still preparing your payment" in res
            assert "FATAL_ERROR" not in res
