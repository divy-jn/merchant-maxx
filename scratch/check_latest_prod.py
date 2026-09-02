import os
import json
from supabase import create_client

def check():
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    print("--- Users ---")
    users = supabase_admin.table("users").select("*").order("created_at", desc=True).limit(5).execute()
    for u in users.data:
        print(u)
        
    print("\n--- Purchase Intents ---")
    intents = supabase_admin.table("purchase_intents").select("*").order("created_at", desc=True).limit(5).execute()
    for i in intents.data:
        print(i)
        
if __name__ == "__main__":
    check()
