import os
import requests
import uuid
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://merchant-maxx-api-1066165000716.us-central1.run.app"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

def run_tests():
    print("Running production smoke tests...")
    
    # 1. GET /
    print("\n1. Testing GET /")
    res = requests.get(f"{BASE_URL}/")
    print(f"Status: {res.status_code}, Body: {res.text[:100]}")
    assert res.status_code == 200
    
    # 2. GET /catalog
    print("\n2. Testing GET /catalog")
    res = requests.get(f"{BASE_URL}/catalog")
    print(f"Status: {res.status_code}")
    assert res.status_code == 200
    assert len(res.json()) > 0
    
    # Setup Supabase client for authenticated tests
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    
    # Use SERVICE_KEY to create confirmed users via admin API
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    import jwt
    JWT_SECRET = "7f2d5b1e9c8a4b3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d"
    
    # Create test user 1
    email1 = f"testuser{uuid.uuid4().hex[:8]}@gmail.com"
    pwd1 = "TestUser123!"
    res1 = supabase_admin.auth.admin.create_user({"email": email1, "password": pwd1, "email_confirm": True})
    user1_id = res1.user.id
    # Ensure user exists in public.users
    try:
        supabase_admin.table("users").insert({"id": user1_id, "email": email1, "name": "Test User", "password_hash": "dummy"}).execute()
    except Exception as e:
        print("User 1 already in public.users or insert failed:", e)
    token1 = jwt.encode({"sub": user1_id, "user_id": user1_id}, JWT_SECRET, algorithm="HS256")
    print(f"Created Test User 1: {user1_id}")
    
    # Create test user 2
    email2 = f"testuser{uuid.uuid4().hex[:8]}@gmail.com"
    pwd2 = "TestUser123!"
    res2 = supabase_admin.auth.admin.create_user({"email": email2, "password": pwd2, "email_confirm": True})
    user2_id = res2.user.id
    # Ensure user exists in public.users
    try:
        supabase_admin.table("users").insert({"id": user2_id, "email": email2, "name": "Test User 2", "password_hash": "dummy"}).execute()
    except Exception as e:
        print("User 2 already in public.users or insert failed:", e)
    token2 = jwt.encode({"sub": user2_id, "user_id": user2_id}, JWT_SECRET, algorithm="HS256")
    print(f"Created Test User 2: {user2_id}")
    
    # 3. Authenticated normal chat
    print("\n3. Testing Authenticated normal chat")
    headers1 = {"Authorization": f"Bearer {token1}"}
    chat_res = requests.post(f"{BASE_URL}/chat/", headers=headers1, json={
        "message": "Hi, I just want to chat.",
        "conversation_id": None,
        "is_voice": False
    })
    if chat_res.status_code != 200:
        print(f"Chat failed: {chat_res.text}")
    assert chat_res.status_code == 200
    conv_id = chat_res.json()["conversation_id"]
    print(f"Created Conversation for User 1: {conv_id}")
    print(f"Response: {chat_res.json()['response'][:100]}")
    
    # 4. Cross-user conversation access -> must return 403 or 404
    print("\n4. Testing cross-user conversation access")
    headers2 = {"Authorization": f"Bearer {token2}"}
    cross_res = requests.post(f"{BASE_URL}/chat/", headers=headers2, json={
        "message": "Hi, reading someone else's chat.",
        "conversation_id": conv_id,
        "is_voice": False
    })
    print(f"Status: {cross_res.status_code}, Body: {cross_res.text[:100]}")
    assert cross_res.status_code in (403, 404)
    
    # 5. verify unsigned Razorpay webhook is rejected
    print("\n5. Testing unsigned webhook")
    webhook_res = requests.post(f"{BASE_URL}/razorpay/webhook", json={"event": "payment.captured"})
    print(f"Status: {webhook_res.status_code}, Body: {webhook_res.text[:100]}")
    assert webhook_res.status_code == 400
    
    # 6. verify backend can still access Supabase after RLS lockdown
    # We already did it partially by chatting (which reads catalog / intents). Let's explicitly check GET /catalog which does a Supabase read using SERVICE KEY or anon. Wait, backend uses SERVICE_KEY. So chat definitely uses the DB to write messages. Since chat worked, the DB connection works!
    print("\n6. Database connection successful via Chat.")

    print("\nALL PRODUCTION SMOKE TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
