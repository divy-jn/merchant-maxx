import asyncio
import os
import uuid

from utils.supabase_client import supabase

def test_is_null():
    intent_id = f"pi_{uuid.uuid4().hex[:12]}"
    conv_id = str(uuid.uuid4())
    supabase.table("conversations").insert({"id": conv_id, "title": "test"}).execute()
    data = {
        "purchase_intent_id": intent_id,
        "conversation_id": conv_id,
        "purchase_state": "PRODUCT_SELECTED",
        "user_confirmed": True,
        "basket": [{"product_id": "item_laptop", "quantity": 1}],
        "amount_paise": 50000,
        "razorpay_order_id": None
    }
    supabase.table("purchase_intents").insert(data).execute()

    res = supabase.table("purchase_intents").update({
        "basket": [{"product_id": "item_mouse", "quantity": 1}],
        "amount_paise": 5000,
        "purchase_state": "PRODUCT_SELECTED",
        "user_confirmed": False
    }).eq("purchase_intent_id", intent_id).is_("razorpay_order_id", "null").in_("purchase_state", ["IDLE", "PRODUCT_SELECTED", "RECOMMENDATION_SHOWN", "PURCHASE_PENDING", "USER_CONFIRMED", "PAYMENT_FAILED", "PAYMENT_UNKNOWN", "RECOVERY_PENDING"]).execute()
    
    print("UPDATE MATCHES:", len(res.data) if res.data else 0)
    print("RES.DATA:", res.data)

if __name__ == "__main__":
    test_is_null()
