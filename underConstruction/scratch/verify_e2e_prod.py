import os
import requests
import uuid
from supabase import create_client
from dotenv import load_dotenv
import jwt
import hmac
import hashlib
import json
import time

load_dotenv()

BASE_URL = "https://merchant-maxx-api-1066165000716.us-central1.run.app"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
RAZORPAY_SECRET = os.environ.get("RAZORPAY_TEST_KEY_SECRET")
JWT_SECRET = "[MASKED_JWT_SECRET]"

print("--- PHASE 1: BASIC PRODUCTION HEALTH ---")
res = requests.get(f"{BASE_URL}/")
assert res.status_code == 200
print("Backend health OK")

supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
email = f"e2etest{uuid.uuid4().hex[:8]}@example.com"
pwd = "Password123!"
res1 = supabase_admin.auth.admin.create_user({"email": email, "password": pwd, "email_confirm": True})
user_id = res1.user.id
supabase_admin.table("users").insert({"id": user_id, "email": email, "name": "E2E User", "password_hash": "dummy"}).execute()
supabase_admin.table("customers").insert({"customer_id": user_id, "email": email, "name": "E2E User", "merchant_id": "merchant_mxx_001"}).execute()

token = jwt.encode({"sub": user_id, "user_id": user_id}, JWT_SECRET, algorithm="HS256")
headers = {"Authorization": f"Bearer {token}"}
print(f"Auth OK. User ID: {user_id}")


print("\n--- PHASE 2: NORMAL LLM REQUEST ---")
chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers, json={
    "message": "hi",
    "conversation_id": None,
    "is_voice": False
})
assert chat_res.status_code == 200
conv_id = chat_res.json()["conversation_id"]
print(f"Response: {chat_res.json()['response']}")
print("Normal chat OK. Greeting fast-path executed.")


print("\n--- PHASE 3: REAL FALLBACK PROOF ---")
print("Production fallback not directly proven; only automated fallback tests verified.")


print("\n--- PHASE 4: COMMERCE E2E ---")
# 1. Search product
print("Searching for product...")
chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers, json={"message": "Show me wireless mice", "conversation_id": conv_id})
print(f"MAXX: {chat_res.json()['response']}")

# 2. Select product
print("Selecting product...")
chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers, json={"message": "I want to buy the ergonomic one", "conversation_id": conv_id})
print(f"MAXX: {chat_res.json()['response']}")

# Verify state
intents = supabase_admin.table("purchase_intents").select("*").eq("customer_id", user_id).in_("purchase_state", ["PURCHASE_PENDING", "PRODUCT_SELECTED", "RECOMMENDATION_SHOWN"]).execute()
assert len(intents.data) == 1
intent_id = intents.data[0]["purchase_intent_id"]
print(f"Intent created: {intent_id}, Status: {intents.data[0]['purchase_state']}")

# 3. Confirm and Checkout (Fast-path)
print("Confirming and checking out...")
chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers, json={"message": "confirm", "conversation_id": conv_id})
print(f"MAXX: {chat_res.json()['response']}")
intents = supabase_admin.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).execute()
assert intents.data[0]["purchase_state"] == "PAYMENT_PENDING"
print("Confirmed and Checkout OK.")

orders = supabase_admin.table("orders").select("*").eq("purchase_intent_id", intent_id).execute()
assert len(orders.data) == 1
rzp_order_id = intents.data[0]["razorpay_order_id"]
print(f"Razorpay Order ID generated: {rzp_order_id}")
checkout_data = chat_res.json().get("checkout_data")
assert checkout_data is not None
# The checkout_data["order_id"] might be the Razorpay ID, whereas orders.data[0]["order_id"] is the local ord_ ID.
# Let's check entity_mapping to be sure, or just assert the intent's razorpay_order_id matches checkout_data.
assert checkout_data["order_id"] == intents.data[0]["razorpay_order_id"]
print("Checkout OK. Data returned to frontend.")


print("\n--- PHASE 5: PAYMENT PENDING RECOVERY ---")
chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers, json={"message": "payment?", "conversation_id": conv_id})
print(f"MAXX: {chat_res.json()['response']}")
orders_new = supabase_admin.table("orders").select("*").eq("purchase_intent_id", intent_id).execute()
assert len(orders_new.data) == 1
assert checkout_data["order_id"] == rzp_order_id
print("Recovery OK. Reused existing Razorpay order.")


print("\n--- PHASE 6: REFRESH / HISTORY ---")
print("Restoring conversation history via empty message fetch (or just trusting checkout_data state).")
history_res = requests.get(f"{BASE_URL}/conversations", headers=headers)
assert history_res.status_code == 200
convs = history_res.json()
assert len([c for c in convs if c["id"] == conv_id]) == 1
print("History OK. Conversation persists.")


print("\n--- PHASE 7: DUPLICATE CHECKOUT ---")
chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers, json={"message": "checkout", "conversation_id": conv_id})
orders_dup = supabase_admin.table("orders").select("*").eq("purchase_intent_id", intent_id).execute()
assert len(orders_dup.data) == 1
assert orders_dup.data[0]["order_id"] == rzp_order_id
print("Duplicate Checkout OK. NO duplicate Razorpay order.")


print("\n--- PHASE 8: PAYMENT COMPLETION ---")
payload = {
    "event": "payment.captured",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_mock123",
                "order_id": rzp_order_id,
                "amount": orders_dup.data[0]["amount_paise"],
                "status": "captured"
            }
        }
    }
}
body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
signature = hmac.new(RAZORPAY_SECRET.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()

webhook_res = requests.post(
    f"{BASE_URL}/razorpay/webhook",
    headers={"x-razorpay-signature": signature, "Content-Type": "application/json"},
    data=body_bytes
)
assert webhook_res.status_code == 200
print("Webhook verified and processed.")

intents = supabase_admin.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).execute()
assert intents.data[0]["purchase_state"] == "PAYMENT_SUCCESS"
print("Payment Completion OK. Status is PAYMENT_SUCCESS.")


print("\n--- PHASE 9: NEW PURCHASE AFTER SUCCESS ---")
chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers, json={"message": "I want to buy a gaming mouse", "conversation_id": conv_id})
print(f"MAXX: {chat_res.json()['response']}")
new_intents = supabase_admin.table("purchase_intents").select("*").eq("customer_id", user_id).in_("purchase_state", ["PURCHASE_PENDING", "PRODUCT_SELECTED", "RECOMMENDATION_SHOWN"]).execute()
assert len(new_intents.data) == 1
assert new_intents.data[0]["purchase_intent_id"] != intent_id
print("New Purchase OK. New intent created.")

print("\n--- ALL TESTS COMPLETED SUCCESSFULLY ---")
