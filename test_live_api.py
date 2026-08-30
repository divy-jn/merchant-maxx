import requests
import json
import uuid
import sys

API_URL = "https://merchant-maxx-api-1066165000716.us-central1.run.app"

session_id = "guest"

def test_chat(message: str):
    global session_id
    print(f"\n--- Sending message: '{message}' ---")
    response = requests.post(f"{API_URL}/chat/", json={
        "message": message,
        "conversation_id": session_id,
        "is_guest": True
    })
    
    if response.status_code != 200:
        print(f"FAILED: {response.status_code}")
        print(response.text)
        return False
        
    data = response.json()
    session_id = data.get("conversation_id")
    print("Response status:", data.get("status"))
    print("Agent reply:", data.get("response"))
    return True

if __name__ == "__main__":
    print(f"Testing API at {API_URL}")
    print(f"Using Session ID: {session_id}")
    
    print("\n1. Basic Chat (Greeting)")
    if not test_chat("Hi, are you ready?"):
        sys.exit(1)
        
    print("\n2. Product Query (Semantic Search)")
    if not test_chat("Do you have shoes?"):
        sys.exit(1)
        
    print("\n3. Multi-turn context")
    if not test_chat("What is the price of the first one you mentioned?"):
        sys.exit(1)
        
    print("\nSUCCESS!")
