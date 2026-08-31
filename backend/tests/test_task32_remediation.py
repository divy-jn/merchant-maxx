import pytest
import subprocess


def test_secret_files_untracked():
    """Verify that known secret files are not tracked in git."""
    secret_files = ["_env_restore.txt", "_env_restore.yaml", "cloud_run_env.json"]
    
    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    tracked_files = result.stdout.splitlines()
    
    for file in secret_files:
        assert file not in tracked_files, f"Secret file {file} is still tracked in git!"

def test_migration_chain():
    """Verify migrations 001 through 007 exist."""
    import os
    migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'db', 'migrations')
    expected_migrations = [
        "001_purchase_intents.sql",
        "002_payment_hardening.sql",
        "003_recommendation_idempotency.sql",
        "004_inventory_fulfillment.sql",
        "005_rls_hardening.sql",
        "006_basket_confirmation.sql",
        "007_payment_state_finality.sql"
    ]
    
    actual_files = os.listdir(migrations_dir)
    for expected in expected_migrations:
        assert expected in actual_files, f"Missing migration: {expected}"

def test_schema_no_permissive_rls():
    """Verify schema.sql does not contain permissive RLS."""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'schema.sql')
    with open(schema_path, 'r') as f:
        content = f.read()
    
    assert "USING (true)" not in content, "schema.sql still contains permissive USING (true) RLS policies"
    assert 'CREATE POLICY "Allow all on' not in content, "schema.sql still contains permissive 'Allow all on' RLS policies"
    
def test_acp_discovery_endpoints_implemented():
    """Verify advertised ACP endpoints actually exist in the FastAPI app."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    response = client.get("/acp/.well-known/agent-commerce.json")
    if response.status_code == 404:
        # maybe it's registered under the root directly
        response = client.get("/.well-known/agent-commerce.json")
    
    assert response.status_code == 200, "Discovery endpoint failed"
    discovery_data = response.json()
    
    # Get all registered routes
    registered_routes = [route.path for route in app.routes]
    
    for capability in discovery_data.get("capabilities", []):
        endpoint = capability.get("endpoint")
        assert endpoint in registered_routes, f"Advertised capability endpoint {endpoint} is not implemented"
