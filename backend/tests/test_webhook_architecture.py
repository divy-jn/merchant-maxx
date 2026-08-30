import pytest
import threading
import time
import uuid
import asyncio
from fastapi import Request
from agents.tools import create_razorpay_order
from routes.webhooks import handle_razorpay_webhook
from utils.supabase_client import supabase
from config import settings
from agents.payment_state import is_terminal

class MockRequest:
    def __init__(self, event, payload):
        self._event = event
        self._payload = payload
        self.client = type("Client", (), {"host": "127.0.0.1"})()
        
    async def body(self):
        import json
        return json.dumps({"event": self._event, "payload": self._payload, "id": f"evt_{uuid.uuid4().hex}"}).encode()
        
    @property
    def headers(self):
        class Headers:
            def get(self, k, default): return {"X-Razorpay-Signature": "sig"}.get(k, default)
        return Headers()
        
    async def json(self):
        return {"event": self._event, "payload": self._payload, "id": f"evt_{uuid.uuid4().hex}"}

def setup_intent_and_order(state="PAYMENT_PENDING", rzp_order_id=None):
    # Setup test data
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    conv_id = str(uuid.uuid4())
    supabase.table("conversations").upsert({"id": conv_id, "title": "test"}).execute()
    rzp_order_id = rzp_order_id or f"order_{uuid.uuid4().hex[:12]}"
    
    # 1. Intent
    supabase.table("purchase_intents").insert({
        "purchase_intent_id": intent_id,
        "conversation_id": conv_id,
        "purchase_state": state,
        "user_confirmed": True,
        "basket": [{"product_id": "item_laptop", "quantity": 1}],
        "amount_paise": 50000,
        "confirmed_basket": [{"product_id": "item_laptop", "quantity": 1}],
        "confirmed_amount_paise": 50000,
        "razorpay_order_id": rzp_order_id
    }).execute()
    
    # 2. Local Order
    local_order_id = f"ord_{uuid.uuid4().hex[:12]}"
    supabase.table("orders").insert({
        "order_id": local_order_id,
        "purchase_intent_id": intent_id,
        "merchant_id": "merchant_mxx_001",
        "status": "CREATED",
        "total_paise": 50000,
        "currency": "INR",
        "purchase_state": state
    }).execute()
    
    # 3. Entity Mapping
    supabase.table("entity_mapping").insert({
        "synthetic_id": local_order_id,
        "entity_type": "order",
        "razorpay_id": rzp_order_id
    }).execute()
    
    return intent_id, rzp_order_id, local_order_id

def test_webhook_toctou_race_condition(monkeypatch):
    """
    Simulate a TOCTOU race condition where `payment.failed` arrives slightly after `order.paid`.
    We want to ensure that `PAYMENT_SUCCESS` is never overwritten by `PAYMENT_FAILED`.
    """
    import routes.webhooks
    monkeypatch.setattr(routes.webhooks.rzp.utility, "verify_webhook_signature", lambda b, s, x: None)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "test_secret")

    intent_id, rzp_order_id, local_order_id = setup_intent_and_order("PAYMENT_PENDING")
    
    # We will simulate a race by patching can_transition to sleep on the failed thread
    # so that the success thread completes its update first!
    original_can_transition = routes.webhooks.can_transition
    
    def delayed_can_transition(from_state, to_state):
        if to_state == "PAYMENT_FAILED":
            time.sleep(0.5) # Force it to lag behind the SUCCESS update
        return original_can_transition(from_state, to_state)
        
    monkeypatch.setattr(routes.webhooks, "can_transition", delayed_can_transition)

    def success_thread():
        req = MockRequest("order.paid", {"order": {"entity": {"id": rzp_order_id}}, "payment": {"entity": {"order_id": rzp_order_id, "id": "pay_1", "amount": 50000}}})
        asyncio.run(handle_razorpay_webhook(req))
        
    def failure_thread():
        time.sleep(0.1) # Start slightly after to ensure they read PAYMENT_PENDING concurrently
        req = MockRequest("payment.failed", {"payment": {"entity": {"order_id": rzp_order_id, "id": "pay_2", "amount": 50000}}})
        asyncio.run(handle_razorpay_webhook(req))
        
    t1 = threading.Thread(target=success_thread)
    t2 = threading.Thread(target=failure_thread)
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # Assert state is SUCCESS
    intent = supabase.table("purchase_intents").select("purchase_state").eq("purchase_intent_id", intent_id).execute().data[0]
    assert intent["purchase_state"] == "PAYMENT_SUCCESS"

def test_create_razorpay_order_fails_if_local_persistence_fails(monkeypatch):
    """
    If local order creation fails (e.g., mapping fails), create_razorpay_order MUST return failure.
    """
    import agents.tools
    import razorpay_service.orders
    monkeypatch.setattr(razorpay_service.orders, "create_order", lambda *a, **k: {"id": "order_rzp_mock"})
    
    import agents.guardian
    monkeypatch.setattr(agents.guardian, "validate_action", lambda *a, **k: [({"product_id": "item_laptop"}, 1, 50000, 50000)])
    
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    conv_id = str(uuid.uuid4())
    supabase.table("conversations").upsert({"id": conv_id, "title": "test"}).execute()
    supabase.table("purchase_intents").insert({
        "purchase_intent_id": intent_id,
        "conversation_id": conv_id,
        "purchase_state": "USER_CONFIRMED",
        "user_confirmed": True,
        "basket": [{"product_id": "item_laptop", "quantity": 1}],
        "amount_paise": 50000,
        "confirmed_basket": [{"product_id": "item_laptop", "quantity": 1}],
        "confirmed_amount_paise": 50000
    }).execute()
    
    # Mock supabase to fail on insert to orders
    original_table = agents.tools.supabase.table
    def fail_orders_table(name):
        t = original_table(name)
        if name == "orders":
            t.insert = lambda *a, **k: (_ for _ in ()).throw(Exception("DB Insert Failed!"))
        return t
        
    monkeypatch.setattr(agents.tools.supabase, "table", fail_orders_table)
    
    res = create_razorpay_order.invoke({
        "state": {"session_id": conv_id, "purchase_context": {"purchase_intent_id": intent_id, "basket": [{"product_id": "item_laptop", "quantity": 1}], "amount_paise": 50000}},
    })
    
    assert "internal error while mapping data" in res
    
    # Check that state was rolled back to USER_CONFIRMED
    intent = supabase.table("purchase_intents").select("purchase_state, razorpay_order_id").eq("purchase_intent_id", intent_id).execute().data[0]
    assert intent["purchase_state"] == "USER_CONFIRMED"
    assert intent["razorpay_order_id"] is None

def test_webhook_fallback_to_intent_id_without_entity_mapping(monkeypatch):
    """
    Test that the webhook falls back to using the purchase_intent table if entity_mapping is missing.
    """
    import routes.webhooks
    monkeypatch.setattr(routes.webhooks.rzp.utility, "verify_webhook_signature", lambda b, s, x: None)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "test_secret")
    
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    rzp_order_id = f"order_{uuid.uuid4().hex[:12]}"
    supabase.table("purchase_intents").insert({
        "purchase_intent_id": intent_id,
        "purchase_state": "PAYMENT_PENDING",
        "razorpay_order_id": rzp_order_id
    }).execute()
    
    # Notice: NO entity_mapping OR orders row
    req = MockRequest("payment.captured", {"payment": {"entity": {"order_id": rzp_order_id, "id": "pay_fallback", "amount": 50000}}})
    res = asyncio.run(handle_razorpay_webhook(req))
    
    # Since order is missing, it will bypass amount validation because order is None,
    # and bypass payment persistence. BUT it should still update the intent!
    intent = supabase.table("purchase_intents").select("purchase_state").eq("purchase_intent_id", intent_id).execute().data[0]
    assert intent["purchase_state"] == "PAYMENT_SUCCESS"
    assert res == {"status": "ok"}
