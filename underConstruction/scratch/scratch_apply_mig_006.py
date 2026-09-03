import os
from supabase import create_client
import sys
from dotenv import load_dotenv
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("Missing env")
    sys.exit(1)

supabase = create_client(url, key)

with open("backend/db/migrations/006_basket_confirmation.sql", "r") as f:
    sql = f.read()

res = supabase.rpc("exec_sql", {"sql": sql}).execute()
print(res)
