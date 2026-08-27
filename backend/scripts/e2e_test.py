import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("API_URL", "http://localhost:8000")

async def test_agent_flow():
    print("=== Starting E2E Tests ===")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        # 1. Health check
        print("\n1. Checking API health...")
        resp = await client.get("/")
        print(f"Health Check: {resp.status_code}")
        if resp.status_code != 200:
            print("❌ Backend is not running on localhost:8000")
            return
            
        # 2. Get Catalog
        print("\n2. Fetching Catalog...")
        resp = await client.get("/catalog/")
        print(f"Catalog Status: {resp.status_code}")
        catalog = resp.json()
        print(f"Found {len(catalog)} items in catalog")
        
        # 3. Test Agent Chat (Simulating a user wanting to buy something)
        print("\n3. Testing MAXX Chat (Intent: Buy Headphones)...")
        chat_payload = {
            "session_id": "test_e2e_session_001",
            "message": "I want to buy the Sony headphones. Can you give me a checkout link?"
        }
        resp = await client.post("/chat/", json=chat_payload)
        print(f"Chat Response Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"MAXX replied: {data.get('response', '')[:100]}...")
        else:
            print(f"❌ Chat failed: {resp.text}")
            
        # 4. Check Audit Logs for Guardian Activity
        print("\n4. Checking Audit Logs (Ledger/Guardian)...")
        resp = await client.get("/audit/")
        if resp.status_code == 200:
            logs = resp.json()
            print(f"Found {len(logs)} audit logs.")
            # Print the latest log
            if logs:
                latest = logs[0]
                print(f"Latest action: [{latest.get('agent_name')}] - {latest.get('action')}")
                print(f"Reasoning: {latest.get('reasoning')[:100]}...")
        else:
            print(f"❌ Audit log fetch failed: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_agent_flow())
