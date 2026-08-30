import pytest
import threading
import time
import uuid
from agents.tools import stage_purchase_intent, create_razorpay_order
from agents.scout import scout_node
import agents.scout
from langchain_core.messages import AIMessage, ToolMessage
from utils.supabase_client import supabase

class MockLLM:
    def bind_tools(self, tools): return self
    def invoke(self, messages):
        return AIMessage(content="", tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_mouse", "quantity": 1}, "id": "call_1"}])

def setup_intent(state="USER_CONFIRMED", razorpay_order_id=None):
    # Ensure test products exist
    try:
        supabase.table("products").upsert([
            {"product_id": "item_laptop", "merchant_id": "merchant_mxx_001", "name": "Test Laptop", "price_paise": 50000, "active": True, "inventory_qty": 10},
            {"product_id": "item_mouse", "merchant_id": "merchant_mxx_001", "name": "Test Mouse", "price_paise": 5000, "active": True, "inventory_qty": 10}
        ]).execute()
    except Exception as e:
        print("Failed to setup products:", e)

    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    conv_id = str(uuid.uuid4())
    supabase.table("conversations").insert({"id": conv_id, "title": "test"}).execute()
    data = {
        "purchase_intent_id": intent_id,
        "conversation_id": conv_id,
        "purchase_state": state,
        "user_confirmed": True,
        "basket": [{"product_id": "item_laptop", "quantity": 1}],
        "amount_paise": 50000
    }
    if razorpay_order_id:
        data["razorpay_order_id"] = razorpay_order_id
    supabase.table("purchase_intents").insert(data).execute()
    return intent_id, conv_id

def test_toctou_race_condition(monkeypatch):
    """
    Simulates concurrent Scout modification and Order creation.
    With the atomic locking in place, Scout should fail to modify the existing intent
    and should clone it instead.
    """
    intent_id, conv_id = setup_intent()

    def mock_create_order(*args, **kwargs):
        time.sleep(1) # Simulated network delay
        return {"id": f"order_{uuid.uuid4().hex[:12]}"}

    import razorpay_service.orders
    monkeypatch.setattr(razorpay_service.orders, "create_order", mock_create_order)
    import agents.guardian
    monkeypatch.setattr(agents.guardian, "validate_action", lambda *a, **k: None)
    monkeypatch.setattr(agents.scout, "get_llm", lambda: MockLLM())

    closer_result = []
    def closer_thread():
        state = {"purchase_context": {"purchase_intent_id": intent_id, "basket_items": [{"product_id": "item_laptop", "quantity": 1}]}, "purchase_state": "USER_CONFIRMED", "user_confirmed": True}
        res = create_razorpay_order.invoke({"state": state})
        closer_result.append(res)
        
    scout_result = []
    def scout_thread():
        time.sleep(0.3) # Wait for closer to reserve the intent
        state = {"purchase_context": {"purchase_intent_id": intent_id, "basket_items": [{"product_id": "item_laptop", "quantity": 1}]}, "session_id": conv_id, "messages": [ToolMessage(content="Product ID: item_mouse", tool_call_id="call_1")]}
        scout_node(state)
        scout_result.append(True)

    t1 = threading.Thread(target=closer_thread)
    t2 = threading.Thread(target=scout_thread)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).execute().data[0]
    
    # Assert that the old intent was NOT mutated (basket size 1, has order ID)
    assert len(intent.get("basket", [])) == 1
    assert intent.get("razorpay_order_id") is not None
    assert intent.get("purchase_state") == "PAYMENT_PENDING"

    # A new intent should have been created with the new basket (laptop + mouse)
    new_intents = supabase.table("purchase_intents").select("*").eq("conversation_id", conv_id).neq("purchase_intent_id", intent_id).execute().data
    assert len(new_intents) == 1
    new_intent = new_intents[0]
    assert len(new_intent.get("basket", [])) == 2
    assert new_intent.get("razorpay_order_id") is None

def test_normal_unlocked_basket_mutation(monkeypatch):
    monkeypatch.setattr(agents.scout, "get_llm", lambda: MockLLM())
    intent_id, conv_id = setup_intent("PRODUCT_SELECTED")
    state = {"purchase_context": {"purchase_intent_id": intent_id, "basket_items": [{"product_id": "item_laptop", "quantity": 1}]}, "session_id": conv_id, "messages": [ToolMessage(content="Product ID: item_mouse", tool_call_id="call_0")]}
    scout_node(state)
    intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).execute().data[0]
    assert len(intent.get("basket", [])) == 2

def test_locked_intent_mutation_creates_clone(monkeypatch):
    monkeypatch.setattr(agents.scout, "get_llm", lambda: MockLLM())
    intent_id, conv_id = setup_intent("PAYMENT_PENDING", razorpay_order_id="order_123")
    state = {"purchase_context": {"purchase_intent_id": intent_id, "basket_items": [{"product_id": "item_laptop", "quantity": 1}]}, "session_id": conv_id, "messages": [ToolMessage(content="Product ID: item_mouse", tool_call_id="call_0")]}
    scout_node(state)
    
    intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).execute().data[0]
    assert len(intent.get("basket", [])) == 1 # Old unmodified
    
    new_intents = supabase.table("purchase_intents").select("*").eq("conversation_id", conv_id).neq("purchase_intent_id", intent_id).execute().data
    assert len(new_intents) == 1
    assert len(new_intents[0].get("basket", [])) == 2 # New modified

def test_razorpay_api_failure_does_not_corrupt(monkeypatch):
    intent_id, conv_id = setup_intent()
    def mock_create_order_fail(*args, **kwargs):
        raise Exception("API failure")

    import razorpay_service.orders
    monkeypatch.setattr(razorpay_service.orders, "create_order", mock_create_order_fail)
    import agents.guardian
    monkeypatch.setattr(agents.guardian, "validate_action", lambda *a, **k: None)

    state = {"purchase_context": {"purchase_intent_id": intent_id, "basket_items": [{"product_id": "item_laptop", "quantity": 1}]}, "purchase_state": "USER_CONFIRMED", "user_confirmed": True}
    res = create_razorpay_order.invoke({"state": state})
    
    intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).execute().data[0]
    # State should revert to USER_CONFIRMED since Razorpay failed
    assert intent.get("purchase_state") == "USER_CONFIRMED"
    assert "failed due to a temporary error" in res

def test_terminal_payment_success_cannot_be_mutated(monkeypatch):
    monkeypatch.setattr(agents.scout, "get_llm", lambda: MockLLM())
    intent_id, conv_id = setup_intent("PAYMENT_SUCCESS", razorpay_order_id="order_xyz")
    state = {"purchase_context": {"purchase_intent_id": intent_id, "basket_items": [{"product_id": "item_laptop", "quantity": 1}]}, "session_id": conv_id, "messages": [ToolMessage(content="Product ID: item_mouse", tool_call_id="call_0")]}
    scout_node(state)
    
    intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).execute().data[0]
    assert len(intent.get("basket", [])) == 1
    assert intent.get("purchase_state") == "PAYMENT_SUCCESS"
