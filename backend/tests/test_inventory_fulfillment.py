import pytest
import threading
import uuid
import time
from utils.supabase_client import supabase

def setup_inventory_test():
    # Setup fresh products for test
    pid1 = f"inv_item_{uuid.uuid4().hex[:6]}"
    pid2 = f"inv_item_{uuid.uuid4().hex[:6]}"
    
    supabase.table("products").upsert([
        {"product_id": pid1, "merchant_id": "merchant_mxx_001", "name": "Item 1", "price_paise": 1000, "active": True, "inventory_qty": 5},
        {"product_id": pid2, "merchant_id": "merchant_mxx_001", "name": "Item 2", "price_paise": 2000, "active": True, "inventory_qty": 1},
    ]).execute()
    
    return pid1, pid2

def test_atomic_inventory_decrement_success():
    pid1, pid2 = setup_inventory_test()
    order_id = f"order_{uuid.uuid4().hex[:12]}"
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    
    basket = [
        {"product_id": pid1, "quantity": 3},
        {"product_id": pid2, "quantity": 1}
    ]
    
    # 1. Execute decrement
    res = supabase.rpc("atomic_inventory_decrement", {
        "p_order_id": order_id,
        "p_intent_id": intent_id,
        "p_items": basket
    }).execute()
    
    assert res.data["status"] == "success"
    
    # 2. Verify decrement
    p1 = supabase.table("products").select("inventory_qty").eq("product_id", pid1).single().execute()
    p2 = supabase.table("products").select("inventory_qty").eq("product_id", pid2).single().execute()
    
    assert p1.data["inventory_qty"] == 2  # 5 - 3 = 2
    assert p2.data["inventory_qty"] == 0  # 1 - 1 = 0
    
    # 3. Test idempotency (duplicate call)
    res_dup = supabase.rpc("atomic_inventory_decrement", {
        "p_order_id": order_id,
        "p_intent_id": intent_id,
        "p_items": basket
    }).execute()
    
    assert res_dup.data["status"] == "already_processed"
    
    # Verify no double decrement
    p1_dup = supabase.table("products").select("inventory_qty").eq("product_id", pid1).single().execute()
    assert p1_dup.data["inventory_qty"] == 2

def test_atomic_inventory_decrement_failure_rollback():
    pid1, pid2 = setup_inventory_test()
    order_id = f"order_{uuid.uuid4().hex[:12]}"
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    
    # Basket where pid2 asks for 2 but only 1 exists
    basket = [
        {"product_id": pid1, "quantity": 3},
        {"product_id": pid2, "quantity": 2}
    ]
    
    # Because of atomic failure, the RPC should raise an exception
    with pytest.raises(Exception) as excinfo:
        supabase.rpc("atomic_inventory_decrement", {
            "p_order_id": order_id,
            "p_intent_id": intent_id,
            "p_items": basket
        }).execute()
    
    assert "Insufficient inventory" in str(excinfo.value)
    
    # Verify ALL-OR-NOTHING (pid1 should NOT be decremented)
    p1 = supabase.table("products").select("inventory_qty").eq("product_id", pid1).single().execute()
    assert p1.data["inventory_qty"] == 5

def test_concurrent_inventory_decrement():
    pid1, _ = setup_inventory_test()
    # Explicitly set inventory to 3
    supabase.table("products").update({"inventory_qty": 3}).eq("product_id", pid1).execute()
    
    results = []
    
    def buy_3(order_id):
        try:
            res = supabase.rpc("atomic_inventory_decrement", {
                "p_order_id": order_id,
                "p_intent_id": f"pi_{uuid.uuid4().hex[:8]}",
                "p_items": [{"product_id": pid1, "quantity": 3}]
            }).execute()
            results.append(res.data)
        except Exception as e:
            results.append(str(e))
            
    t1 = threading.Thread(target=buy_3, args=(f"order_{uuid.uuid4().hex[:8]}",))
    t2 = threading.Thread(target=buy_3, args=(f"order_{uuid.uuid4().hex[:8]}",))
    
    t1.start(); t2.start()
    t1.join(); t2.join()
    
    # One should succeed, one should fail
    successes = [r for r in results if isinstance(r, dict) and r.get("status") == "success"]
    failures = [r for r in results if isinstance(r, str) and "Insufficient inventory" in r]
    
    assert len(successes) == 1
    assert len(failures) == 1
    
    p1 = supabase.table("products").select("inventory_qty").eq("product_id", pid1).single().execute()
    assert p1.data["inventory_qty"] == 0

def test_webhook_integration_success(monkeypatch):
    from routes.webhooks import handle_razorpay_webhook
    import razorpay_service.client
    import asyncio
    from fastapi import Request
    
    pid1, _ = setup_inventory_test()
    # set to 1
    supabase.table("products").update({"inventory_qty": 1}).eq("product_id", pid1).execute()
    
    order_id = f"order_{uuid.uuid4().hex[:12]}"
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    pay_id = f"pay_{uuid.uuid4().hex[:8]}"
    
    supabase.table("orders").insert({
        "order_id": order_id,
        "status": "created",
        "total_paise": 1000,
        "purchase_intent_id": intent_id
    }).execute()
    
    supabase.table("entity_mapping").insert({
        "synthetic_id": order_id, "entity_type": "order", "razorpay_id": order_id
    }).execute()
    
    supabase.table("purchase_intents").insert({
        "purchase_intent_id": intent_id,
        "purchase_state": "PAYMENT_PENDING",
        "basket": [{"product_id": pid1, "quantity": 1}],
        "amount_paise": 1000
    }).execute()
    
    monkeypatch.setattr(razorpay_service.client.rzp.utility, "verify_webhook_signature", lambda *a, **k: True)
    
    class MockRequest:
        def __init__(self, json_data):
            self.json_data = json_data
            self.headers = {"X-Razorpay-Signature": "dummy"}
            self.client = type("Client", (), {"host": "127.0.0.1"})()
        async def json(self): return self.json_data
        async def body(self): return b"{}"
    
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "order_id": order_id,
                    "id": pay_id,
                    "amount": 1000
                }
            }
        }
    }
    
    asyncio.run(handle_razorpay_webhook(MockRequest(payload)))
    
    p1 = supabase.table("products").select("inventory_qty").eq("product_id", pid1).single().execute()
    assert p1.data["inventory_qty"] == 0
    
    intent = supabase.table("purchase_intents").select("purchase_state, fulfillment_status").eq("purchase_intent_id", intent_id).single().execute()
    assert intent.data["purchase_state"] == "PAYMENT_SUCCESS"
    assert intent.data["fulfillment_status"] == "FULFILLED"

def test_webhook_integration_insufficient_inventory(monkeypatch):
    from routes.webhooks import handle_razorpay_webhook
    import razorpay_service.client
    import asyncio
    
    pid1, _ = setup_inventory_test()
    # set to 0
    supabase.table("products").update({"inventory_qty": 0}).eq("product_id", pid1).execute()
    
    order_id = f"order_{uuid.uuid4().hex[:12]}"
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    pay_id = f"pay_{uuid.uuid4().hex[:8]}"
    
    supabase.table("orders").insert({
        "order_id": order_id,
        "status": "created",
        "total_paise": 1000,
        "purchase_intent_id": intent_id
    }).execute()
    
    supabase.table("entity_mapping").insert({
        "synthetic_id": order_id, "entity_type": "order", "razorpay_id": order_id
    }).execute()
    
    supabase.table("purchase_intents").insert({
        "purchase_intent_id": intent_id,
        "purchase_state": "PAYMENT_PENDING",
        "basket": [{"product_id": pid1, "quantity": 1}],
        "amount_paise": 1000
    }).execute()
    
    monkeypatch.setattr(razorpay_service.client.rzp.utility, "verify_webhook_signature", lambda *a, **k: True)
    
    # Mock Refund service
    refund_called = []
    def mock_initiate_refund(payment_id, rzp_payment_id, order_id, customer_id, amt, reason, *args, **kwargs):
        refund_called.append((rzp_payment_id, amt))
        return True
    
    import services.refund_service
    monkeypatch.setattr(services.refund_service, "initiate_refund", mock_initiate_refund)
    
    class MockRequest:
        def __init__(self, json_data):
            self.json_data = json_data
            self.headers = {"X-Razorpay-Signature": "dummy"}
            self.client = type("Client", (), {"host": "127.0.0.1"})()
        async def json(self): return self.json_data
        async def body(self): return b"{}"
    
    payload = {
        "event": "payment.captured",
        "id": f"evt_{uuid.uuid4().hex[:8]}",
        "payload": {
            "payment": {
                "entity": {
                    "order_id": order_id,
                    "id": pay_id,
                    "amount": 1000
                }
            }
        }
    }
    
    asyncio.run(handle_razorpay_webhook(MockRequest(payload)))
    
    p1 = supabase.table("products").select("inventory_qty").eq("product_id", pid1).single().execute()
    assert p1.data["inventory_qty"] == 0 # Remained 0
    
    intent = supabase.table("purchase_intents").select("purchase_state, fulfillment_status").eq("purchase_intent_id", intent_id).single().execute()
    assert intent.data["purchase_state"] == "PAYMENT_SUCCESS"
    assert intent.data["fulfillment_status"] == "UNFULFILLED"
    
    assert len(refund_called) == 1
    assert refund_called[0][0] == pay_id
