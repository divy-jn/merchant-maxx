import os
import pytest
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# We MUST use ONLY the ANON key to prove that public access is blocked.
url = os.environ.get("SUPABASE_URL")
anon_key = os.environ.get("SUPABASE_ANON_KEY")
service_key = os.environ.get("SUPABASE_SERVICE_KEY")

@pytest.fixture(scope="module")
def anon_client() -> Client:
    assert url and anon_key, "Supabase URL and Anon Key must be set in .env"
    return create_client(url, anon_key)

@pytest.fixture(scope="module")
def service_client() -> Client:
    assert url and service_key, "Supabase URL and Service Key must be set in .env"
    return create_client(url, service_key)

def test_anon_cannot_read_conversations(anon_client: Client):
    # Should return empty data due to RLS Deny All
    res = anon_client.table("conversations").select("*").limit(1).execute()
    assert len(res.data) == 0

def test_anon_cannot_read_purchase_intents(anon_client: Client):
    res = anon_client.table("purchase_intents").select("*").limit(1).execute()
    assert len(res.data) == 0

def test_anon_cannot_read_orders(anon_client: Client):
    res = anon_client.table("orders").select("*").limit(1).execute()
    assert len(res.data) == 0

def test_anon_cannot_insert_order(anon_client: Client, service_client: Client):
    test_id = "test_anon_insert_123"
    
    # Assert HTTP exception from PostgREST (usually 401 or 403 or empty data depending on setup)
    # Actually, postgrest might just return a 401/403 or an APIError
    try:
        anon_client.table("orders").insert({
            "order_id": test_id,
            "status": "CREATED"
        }).execute()
        pytest.fail("Expected insertion to fail due to RLS")
    except Exception as e:
        # Check underlying state just to be sure
        check = service_client.table("orders").select("*").eq("order_id", test_id).execute()
        assert len(check.data) == 0

def test_anon_cannot_update_inventory(anon_client: Client, service_client: Client):
    # Get a real product ID using service client
    res = service_client.table("products").select("product_id, inventory_qty").limit(1).execute()
    if not res.data:
        pytest.skip("No products found to test update")
    
    pid = res.data[0]["product_id"]
    original_qty = res.data[0]["inventory_qty"]
    
    try:
        update_res = anon_client.table("products").update({"inventory_qty": 9999}).eq("product_id", pid).execute()
        # PostgREST may return empty data on RLS block
        assert len(update_res.data) == 0
    except Exception:
        pass # An exception is also acceptable (e.g. 401/403)
        
    # Verify underlying database state did not change
    check = service_client.table("products").select("inventory_qty").eq("product_id", pid).execute()
    assert check.data[0]["inventory_qty"] == original_qty

def test_anon_cannot_delete_audit_log(anon_client: Client, service_client: Client):
    res = service_client.table("audit_log").select("id").limit(1).execute()
    if not res.data:
        pytest.skip("No audit logs found to test delete")
    
    aid = res.data[0]["id"]
    try:
        del_res = anon_client.table("audit_log").delete().eq("id", aid).execute()
        assert len(del_res.data) == 0
    except Exception:
        pass
        
    # Verify it still exists
    check = service_client.table("audit_log").select("id").eq("id", aid).execute()
    assert len(check.data) == 1

def test_anon_cannot_invoke_inventory_rpc(anon_client: Client):
    payload = {
        "p_order_id": "test_rpc_hack",
        "p_merchant_id": "merchant_mxx_001",
        "p_items": [{"product_id": "prod_0001", "quantity": 1}]
    }
    try:
        anon_client.rpc("atomic_inventory_decrement", payload).execute()
        pytest.fail("Expected RPC invocation to fail")
    except Exception:
        pass # Success, it failed
