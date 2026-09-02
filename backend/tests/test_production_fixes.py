import pytest
import uuid
import os
import json
from unittest.mock import patch, MagicMock

from config import settings
from utils.supabase_client import supabase
from services.payment_resolution import _recover_local_order
from agents.tools import create_razorpay_order
from agents.maxx import maxx_app
from routes.chat import _load_active_intent

# Ensure test DB is used
assert "test" in settings.SUPABASE_URL.lower() or os.environ.get("APP_ENV") == "test", "Tests must run against the test database!"

@pytest.fixture
def mock_customer():
    cid = str(uuid.uuid4())
    supabase.table("users").insert({
        "id": cid,
        "name": "Test User",
        "email": f"{cid[:8]}@example.com",
        "password_hash": "dummy_hash"
    }).execute()
    supabase.table("customers").insert({
        "customer_id": cid,
        "name": "Test User",
        "email": f"{cid[:8]}@example.com"
    }).execute()
    yield cid
    supabase.table("customers").delete().eq("customer_id", cid).execute()
    supabase.table("users").delete().eq("id", cid).execute()

@pytest.fixture
def mock_intent(mock_customer):
    iid = f"pi_{uuid.uuid4().hex[:12]}"
    conv_id = str(uuid.uuid4())
    supabase.table("conversations").insert({"id": conv_id, "title": "Test", "user_id": mock_customer}).execute()
    
    intent = {
        "purchase_intent_id": iid,
        "conversation_id": conv_id,
        "customer_id": mock_customer,
        "purchase_state": "PURCHASE_PENDING",
        "basket": [{"product_id": "test_prod", "quantity": 1}],
        "amount_paise": 10000,
        "user_confirmed": False
    }
    supabase.table("purchase_intents").insert(intent).execute()
    
    yield iid, conv_id
    
    supabase.table("purchase_intents").delete().eq("purchase_intent_id", iid).execute()
    supabase.table("conversations").delete().eq("id", conv_id).execute()

def test_recover_local_order_zero_rows_no_error(mock_intent, mock_customer):
    iid, _ = mock_intent
    # When zero rows exist, it should return None, NOT throw AttributeError
    result = _recover_local_order(iid, "rzp_test_123", mock_customer, 10000, [], 10000, 0, 0)
    assert result is not None
    assert "order_id" in result
    
    # Clean up the created order
    supabase.table("orders").delete().eq("order_id", result["order_id"]).execute()

def test_recover_local_order_existing_reused(mock_intent, mock_customer):
    iid, _ = mock_intent
    
    # Create an order first
    local_id = f"ord_{uuid.uuid4().hex[:12]}"
    supabase.table("orders").insert({
        "order_id": local_id,
        "purchase_intent_id": iid,
        "customer_id": mock_customer,
        "total_paise": 10000
    }).execute()
    
    # Recover should return the existing order
    result = _recover_local_order(iid, "rzp_test_123", mock_customer, 10000, [], 10000, 0, 0)
    assert result is not None
    assert result["order_id"] == local_id
    
    supabase.table("orders").delete().eq("order_id", local_id).execute()

@patch("razorpay_service.orders.create_order")
def test_create_razorpay_order_idempotent_duplicate(mock_create_order, mock_intent, mock_customer):
    iid, conv_id = mock_intent
    
    # Setup intent to be ORDER_CREATING and confirmed
    supabase.table("purchase_intents").update({
        "user_confirmed": True,
        "purchase_state": "USER_CONFIRMED",
        "confirmed_basket": [{"product_id": "test_prod", "quantity": 1}],
        "confirmed_amount_paise": 10000
    }).eq("purchase_intent_id", iid).execute()
    
    # Mock product
    supabase.table("products").upsert({
        "product_id": "test_prod",
        "name": "Test Prod",
        "price_paise": 10000,
        "active": True,
        "inventory_qty": 10,
        "merchant_id": "merchant_mxx_001"
    }).execute()
    
    mock_create_order.return_value = {"id": "order_rzp_123"}
    
    # 1. First creation
    res1 = create_razorpay_order.invoke({"state": {"purchase_context": {"purchase_intent_id": iid}, "session_id": conv_id}})
    assert "Razorpay Order created successfully" in res1
    
    # 2. Reset state back to USER_CONFIRMED to simulate concurrent/duplicate call
    supabase.table("purchase_intents").update({
        "purchase_state": "USER_CONFIRMED"
    }).eq("purchase_intent_id", iid).execute()
    
    # Second creation should trigger unique violation 23505 and recover gracefully
    res2 = create_razorpay_order.invoke({"state": {"purchase_context": {"purchase_intent_id": iid}, "session_id": conv_id}})
    assert "Razorpay Order already exists" in res2
    
    # Clean up
    supabase.table("products").delete().eq("product_id", "test_prod").execute()

def test_load_active_intent_states(mock_intent):
    iid, conv_id = mock_intent
    
    # PAYMENT_PENDING should be restored
    supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_PENDING"}).eq("purchase_intent_id", iid).execute()
    intent = _load_active_intent(conv_id)
    assert intent is not None
    assert intent["purchase_intent_id"] == iid
    
    # PAYMENT_SUCCESS should be excluded (fresh intent)
    supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_SUCCESS"}).eq("purchase_intent_id", iid).execute()
    intent2 = _load_active_intent(conv_id)
    assert intent2 is None
    
@patch("agents.closer.get_llm")
@patch("agents.tools.supabase.table")
def test_create_razorpay_order_fatal_error_stops_graph(mock_table, mock_get_llm, mock_intent):
    iid, conv_id = mock_intent
    
    # Mock an unrecoverable exception
    mock_table.side_effect = Exception("Simulated DB Crash")
    
    from langchain_core.messages import HumanMessage, AIMessage, ToolCall
    from agents.tools import ALL_TOOLS
    import uuid
    
    tool_call = ToolCall(name="create_razorpay_order", args={}, id=str(uuid.uuid4()))
    
    state = {
        "messages": [
            HumanMessage(content="checkout"),
            # Mock the AI calling the tool
            AIMessage(content="", tool_calls=[tool_call])
        ],
        "session_id": conv_id,
        "purchase_state": "USER_CONFIRMED",
        "purchase_context": {"purchase_intent_id": iid}
    }
    
    # The graph should stop and not loop infinitely, ending with the FATAL_ERROR message
    final_state = maxx_app.invoke(state, config={"recursion_limit": 15, "configurable": {"thread_id": conv_id}})
    
    assert final_state["messages"][-1].type == "tool"
    assert "FATAL_ERROR" in final_state["messages"][-1].content

@patch("routes.chat.get_current_user")
def test_history_restores_checkout_data(mock_user, mock_intent):
    iid, conv_id = mock_intent
    uid = supabase.table("conversations").select("user_id").eq("id", conv_id).execute().data[0]["user_id"]
    mock_user.return_value = {"user_id": uid}
    
    supabase.table("purchase_intents").update({
        "purchase_state": "PAYMENT_PENDING",
        "razorpay_order_id": "rzp_test_999"
    }).eq("purchase_intent_id", iid).execute()
    
    from routes.chat import get_chat_history
    history = get_chat_history(conversation_id=conv_id, current_user={"user_id": uid})
    
    assert len(history) > 0
    checkout_msg = history[-1]
    assert checkout_msg["sender"] == "bot"
    assert "checkout_data" in checkout_msg
    assert checkout_msg["checkout_data"]["order_id"] == "rzp_test_999"
