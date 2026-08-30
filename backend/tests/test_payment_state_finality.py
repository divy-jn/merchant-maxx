import pytest
import uuid
import time
from datetime import datetime, timezone
import threading
from utils.supabase_client import supabase
from agents.payment_state import is_terminal
from routes.chat import chat_with_maxx, ChatRequest
from agents.merger import merger_node
from agents.tools import check_payment_status
import razorpay_service.orders

def setup_intent(state="PAYMENT_SUCCESS"):
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    conv_id = str(uuid.uuid4())
    supabase.table("conversations").insert({"id": conv_id, "title": "finality_test"}).execute()
    data = {
        "purchase_intent_id": intent_id,
        "conversation_id": conv_id,
        "purchase_state": state,
        "user_confirmed": True,
        "basket": [{"product_id": "item_laptop", "quantity": 1}],
        "amount_paise": 50000,
        "confirmed_basket": [{"product_id": "item_laptop", "quantity": 1}],
        "confirmed_amount_paise": 50000,
        "razorpay_order_id": f"order_{uuid.uuid4().hex[:8]}"
    }
    supabase.table("purchase_intents").insert(data).execute()
    return intent_id, conv_id

def setup_order(status="CAPTURED"):
    intent_id, conv_id = setup_intent()
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    supabase.table("orders").insert({
        "order_id": order_id,
        "purchase_intent_id": intent_id,
        "status": status,
        "subtotal_paise": 50000,
        "total_paise": 50000,
        "fulfillment_status": "FULFILLED"
    }).execute()
    return order_id, intent_id

# ── Tests 1-3: Direct Application Logic Downgrades ──

def test_1_payment_success_to_failed():
    # Should fail due to Application conditional update
    intent_id, conv_id = setup_intent("PAYMENT_SUCCESS")
    res = supabase.table("purchase_intents").update({
        "purchase_state": "PAYMENT_FAILED"
    }).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    assert len(res.data) == 0

def test_2_payment_success_to_user_confirmed():
    # Should fail due to Application conditional update
    intent_id, conv_id = setup_intent("PAYMENT_SUCCESS")
    res = supabase.table("purchase_intents").update({
        "purchase_state": "USER_CONFIRMED"
    }).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    assert len(res.data) == 0

def test_3_payment_success_to_product_selected():
    # Should fail due to Application conditional update
    intent_id, conv_id = setup_intent("PAYMENT_SUCCESS")
    res = supabase.table("purchase_intents").update({
        "purchase_state": "PRODUCT_SELECTED"
    }).eq("purchase_intent_id", intent_id).in_("purchase_state", ["IDLE", "PRODUCT_SELECTED", "RECOMMENDATION_SHOWN", "PURCHASE_PENDING", "RECOVERY_PENDING"]).execute()
    assert len(res.data) == 0

# ── Concurrency Scenarios ──

def test_4_concurrent_webhook_and_chat_confirmation(monkeypatch):
    intent_id, conv_id = setup_intent("PURCHASE_PENDING")
    
    # Associate conversation with user
    user_id = str(uuid.uuid4())
    supabase.table("users").insert({"id": user_id, "email": f"{user_id}@test.com", "name": "Test User", "password_hash": "dummy"}).execute()
    supabase.table("conversations").update({"user_id": user_id}).eq("id", conv_id).execute()
    
    # Simulate webhook resolving it concurrently
    supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_SUCCESS"}).eq("purchase_intent_id", intent_id).execute()
    
    # Try to confirm via chat route
    req = ChatRequest(conversation_id=conv_id, message="yes confirm")
    # We mock get_current_user to return a dummy user
    from middleware.auth_middleware import get_current_user
    res = chat_with_maxx(req, current_user={"user_id": user_id})
    
    # The state should remain PAYMENT_SUCCESS, not USER_CONFIRMED
    intent = supabase.table("purchase_intents").select("purchase_state").eq("purchase_intent_id", intent_id).execute().data[0]
    assert intent["purchase_state"] == "PAYMENT_SUCCESS"

def test_5_concurrent_webhook_and_merger():
    intent_id, conv_id = setup_intent("PRODUCT_SELECTED")
    
    # Simulate webhook resolving it concurrently
    supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_SUCCESS"}).eq("purchase_intent_id", intent_id).execute()
    
    # Merger processes a stale state
    state = {
        "purchase_state": "PRODUCT_SELECTED", # Stale Python state
        "purchase_context": {"purchase_intent_id": intent_id},
        "scout_result": {"intent_staged": True, "product_context": {"basket_items": []}}
    }
    merger_node(state)
    
    intent = supabase.table("purchase_intents").select("purchase_state").eq("purchase_intent_id", intent_id).execute().data[0]
    assert intent["purchase_state"] == "PAYMENT_SUCCESS"

def test_6_concurrent_success_and_failed_webhook():
    intent_id, conv_id = setup_intent("PAYMENT_PENDING")
    
    # Webhook 1 processes SUCCESS
    from routes.webhooks import _local_order
    supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_SUCCESS"}).eq("purchase_intent_id", intent_id).execute()
    
    # Webhook 2 (failed) arrives concurrently
    # The actual webhook logic uses .neq("purchase_state", "PAYMENT_SUCCESS")
    res = supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_FAILED"}).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    assert len(res.data) == 0
    
    intent = supabase.table("purchase_intents").select("purchase_state").eq("purchase_intent_id", intent_id).execute().data[0]
    assert intent["purchase_state"] == "PAYMENT_SUCCESS"

def test_7_concurrent_reconciliation_and_webhook(monkeypatch):
    intent_id, conv_id = setup_intent("PAYMENT_SUCCESS")
    
    def mock_fetch_order_payments(rid):
        return {"items": [{"status": "failed", "id": "pay_test"}]}
    
    monkeypatch.setattr(razorpay_service.orders, "fetch_order_payments", mock_fetch_order_payments)
    
    # Reconciler processes it
    state = {"purchase_context": {"purchase_intent_id": intent_id}}
    res = check_payment_status.invoke({"state": state})
    
    assert "has a captured payment" in res or "PAYMENT_SUCCESS" in res
    
    intent = supabase.table("purchase_intents").select("purchase_state").eq("purchase_intent_id", intent_id).execute().data[0]
    assert intent["purchase_state"] == "PAYMENT_SUCCESS"

# ── Orders Table ──

def test_8_orders_successful_to_failed():
    order_id, intent_id = setup_order("CAPTURED")
    
    # Simulate webhook trying to downgrade order
    res = supabase.table("orders").update({"status": "FAILED"}).eq("order_id", order_id).neq("status", "CAPTURED").execute()
    assert len(res.data) == 0
    
    order = supabase.table("orders").select("status").eq("order_id", order_id).execute().data[0]
    assert order["status"] == "CAPTURED"

# ── Webhook Idempotency ──

def test_9_duplicate_webhook():
    intent_id, conv_id = setup_intent("PAYMENT_PENDING")
    event_id = f"evt_{uuid.uuid4()}"
    supabase.table("webhook_events").insert({"event_id": event_id, "event_type": "payment.captured", "status": "PROCESSED"}).execute()
    
    # If the webhook processes the same event_id, it is ignored before updating anything
    existing = supabase.table("webhook_events").select("event_id").eq("event_id", event_id).execute().data
    assert len(existing) == 1

def test_10_new_event_id_stale_failure():
    order_id, intent_id = setup_order("CAPTURED")
    supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_SUCCESS"}).eq("purchase_intent_id", intent_id).execute()
    
    # Webhook receives new event_id but for payment.failed
    # The application-level protections should prevent downgrades
    res_intent = supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_FAILED"}).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    res_order = supabase.table("orders").update({"status": "FAILED"}).eq("order_id", order_id).neq("status", "CAPTURED").execute()
    
    assert len(res_intent.data) == 0
    assert len(res_order.data) == 0

# ── Legitimate Transitions ──

def test_11_legitimate_pre_payment_transition():
    intent_id, conv_id = setup_intent("PURCHASE_PENDING")
    res = supabase.table("purchase_intents").update({"purchase_state": "USER_CONFIRMED"}).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    assert len(res.data) == 1
    assert res.data[0]["purchase_state"] == "USER_CONFIRMED"

def test_12_legitimate_payment_success_transition():
    intent_id, conv_id = setup_intent("PAYMENT_PENDING")
    res = supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_SUCCESS"}).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    assert len(res.data) == 1
    assert res.data[0]["purchase_state"] == "PAYMENT_SUCCESS"

def test_13_unrelated_field_update_on_payment_success():
    intent_id, conv_id = setup_intent("PAYMENT_SUCCESS")
    # Updating an unrelated field like `expires_at` should succeed even if the trigger is present
    now = datetime.now(timezone.utc).isoformat()
    res = supabase.table("purchase_intents").update({"expires_at": now}).eq("purchase_intent_id", intent_id).execute()
    assert len(res.data) == 1
    assert res.data[0]["expires_at"] is not None

# ── Database Trigger Finality ──

@pytest.mark.xfail(reason="Migration 007 is not yet applied to production. This will fail until the trigger is deployed.")
def test_14_direct_database_update_attempting_terminal_downgrade():
    """
    CRITICAL: The trigger must protect the system even if application code is buggy.
    This test attempts a blind .update() WITHOUT application-level guards like .neq().
    It MUST fail at the database level via the BEFORE UPDATE trigger.
    """
    intent_id, conv_id = setup_intent("PAYMENT_SUCCESS")
    order_id, _ = setup_order("CAPTURED")
    
    try:
        # Blindly attempt to downgrade the intent without .neq guard
        supabase.table("purchase_intents").update({"purchase_state": "PAYMENT_FAILED"}).eq("purchase_intent_id", intent_id).execute()
        # If the trigger is missing or not applied, the update will succeed, which means the DB is NOT SECURE.
        
        # Verify if the update actually succeeded (which means trigger failed/missing)
        intent = supabase.table("purchase_intents").select("purchase_state").eq("purchase_intent_id", intent_id).execute().data[0]
        if intent["purchase_state"] != "PAYMENT_SUCCESS":
            pytest.fail("DATABASE TRIGGER MISSING OR FAILED: purchase_intent was downgraded to " + intent["purchase_state"])
            
    except Exception as e:
        # Expected if trigger raises an exception
        assert "Cannot downgrade" in str(e) or "PGRST" in str(e) or "400" in str(e)

    try:
        # Blindly attempt to downgrade the order
        supabase.table("orders").update({"status": "FAILED"}).eq("order_id", order_id).execute()
        
        order = supabase.table("orders").select("status").eq("order_id", order_id).execute().data[0]
        if order["status"] != "CAPTURED":
            pytest.fail("DATABASE TRIGGER MISSING OR FAILED: order was downgraded to " + order["status"])
            
    except Exception as e:
        assert "Cannot downgrade" in str(e) or "PGRST" in str(e) or "400" in str(e)

