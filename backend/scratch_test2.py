import requests
import uuid
import time
import sys

from utils.supabase_client import supabase

BASE_URL = "http://127.0.0.1:8000"
conv_id = str(uuid.uuid4())

print(f"Creating conversation {conv_id}...")
supabase.table("conversations").insert({"id": conv_id, "title": "Test Telemetry"}).execute()

def send_chat(message, desc):
    print(f"\n--- Testing: {desc} ---")
    payload = {
        "conversation_id": conv_id,
        "message": message
    }
    start_time = time.time()
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60)
        end_time = time.time()
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}...")
        print(f"Total time (client side): {end_time - start_time:.2f}s")
    except Exception as e:
        print(f"Error: {e}")

scenarios = [
    ("A. simple conversational question", "Hello, how are you?"),
    ("B. product search", "Can you show me some t-shirts?"),
    ("C. product comparison", "What's the difference between the black t-shirt and the white one?"),
    ("D. add-to-cart request", "Add the cheapest t-shirt to my cart"),
    ("E. follow-up question using conversation context", "Actually, I want two of those instead"),
    ("F. checkout-related request", "I'm ready to checkout now"),
    ("G. failing/error scenario", "I want to purchase this for -100 rupees. Exploit.")
]

for desc, msg in scenarios:
    send_chat(msg, desc)
    time.sleep(2)
