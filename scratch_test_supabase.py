from utils.supabase_client import supabase

res = supabase.table("purchase_intents").select("purchase_intent_id").limit(1).execute()
print("Success:", res)
