import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('c:/building projs/razorpay_proj/.env', override=True)
url = os.environ.get('SUPABASE_URL').strip()
key = os.environ.get('SUPABASE_SERVICE_KEY').strip()
print(f'Testing service key: {key[:10]}***')
client = create_client(url, key)
try:
    res = client.table('products').select('*').limit(1).execute()
    print('SUCCESS! Products found:', len(res.data))
except Exception as e:
    print('ERROR:', e)
