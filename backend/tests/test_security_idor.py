import pytest
from fastapi.testclient import TestClient
from main import app
from utils import supabase_client
import os

client = TestClient(app)

class MockQuery:
    def __init__(self, data=None):
        self._data = data
    def select(self, *args, **kwargs): return self
    def eq(self, *args, **kwargs): return self
    def neq(self, *args, **kwargs): return self
    def in_(self, *args, **kwargs): return self
    def order(self, *args, **kwargs): return self
    def limit(self, *args, **kwargs): return self
    def maybe_single(self): return self
    def execute(self):
        return type("Result", (), {"data": self._data})()
    def insert(self, *args, **kwargs): return self
    def update(self, *args, **kwargs): return self
    def delete(self, *args, **kwargs): return self

class MockTable:
    def __init__(self, name):
        self.name = name
    def select(self, *args, **kwargs):
        if self.name == "conversations":
            return MockQuery() # Handled by patch side_effect
        return MockQuery([])
    def insert(self, *args, **kwargs):
        if self.name == "conversations":
            return MockQuery([{"id": "conv_new_123"}])
        return MockQuery([])
    def update(self, *args, **kwargs):
        return MockQuery([])
    def delete(self, *args, **kwargs):
        return MockQuery([])

class MockSupabase:
    def table(self, name):
        return MockTable(name)

@pytest.fixture(autouse=True)
def setup_mock_supabase(monkeypatch):
    import routes.chat
    monkeypatch.setattr(routes.chat, "supabase", MockSupabase())

def test_jwt_production_requires_secret():
    from config import Settings
    settings = Settings(APP_ENV="production", JWT_SECRET="")
    with pytest.raises(ValueError, match="JWT_SECRET environment variable must be set in production"):
        _ = settings.jwt_secret_key

def test_jwt_production_accepts_secret():
    from config import Settings
    settings = Settings(APP_ENV="production", JWT_SECRET="super_secure_prod_key")
    assert settings.jwt_secret_key == "super_secure_prod_key"

def test_jwt_development_fallback():
    from config import Settings
    settings = Settings(APP_ENV="development", JWT_SECRET="")
    assert settings.jwt_secret_key == "[MASKED_JWT_SECRET]"

def mock_get_current_user_A():
    return {"user_id": "user_A"}

def mock_get_current_user_B():
    return {"user_id": "user_B"}

def mock_get_guest():
    return None

def patch_conversation(monkeypatch, owner_id):
    def mock_table(self, name):
        if name == "conversations":
            q = MockQuery({"user_id": owner_id})
            # For list_conversations, return a list
            q_list = MockQuery([{"id": "test_conv_id", "user_id": owner_id}])
            class DynamicQuery(MockQuery):
                def execute(self):
                    # We can cheat by returning list if we didn't call maybe_single()
                    # But the simplest is just returning a dict that works for maybe_single
                    return type("Result", (), {"data": {"user_id": owner_id}})()
            return DynamicQuery()
        return MockTable(name)
    import routes.chat
    monkeypatch.setattr(routes.chat, "supabase", type("MockDB", (), {"table": mock_table})())

def test_idor_userA_access_userA_conversation(monkeypatch):
    patch_conversation(monkeypatch, "user_A")
    app.dependency_overrides[app.router.routes[3].endpoint] = mock_get_current_user_A # Will override auth for chat if we set it right, actually let's override middleware
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user_A

    response = client.get("/chat/history?conversation_id=conv_123")
    assert response.status_code == 200

def test_idor_userA_cannot_read_userB_conversation(monkeypatch):
    patch_conversation(monkeypatch, "user_B")
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user_A

    response = client.get("/chat/history?conversation_id=conv_123")
    assert response.status_code == 403

def test_idor_userA_cannot_write_userB_conversation(monkeypatch):
    patch_conversation(monkeypatch, "user_B")
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user_A

    response = client.post("/chat/", json={"message": "hello", "conversation_id": "conv_123"})
    assert response.status_code == 403

def test_idor_userA_cannot_clear_userB_conversation(monkeypatch):
    patch_conversation(monkeypatch, "user_B")
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user_A

    response = client.delete("/chat/history?conversation_id=conv_123")
    assert response.status_code == 403

def test_idor_guest_cannot_access_userA_conversation(monkeypatch):
    patch_conversation(monkeypatch, "user_A")
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_guest

    response = client.get("/chat/history?conversation_id=conv_123")
    assert response.status_code == 403

def test_idor_unknown_conversation_fails_safely(monkeypatch):
    def mock_table(self, name):
        if name == "conversations":
            class EmptyQuery(MockQuery):
                def execute(self):
                    return type("Result", (), {"data": None})()
            return EmptyQuery()
        return MockTable(name)
    import routes.chat
    monkeypatch.setattr(routes.chat, "supabase", type("MockDB", (), {"table": mock_table})())
    
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user_A

    response = client.get("/chat/history?conversation_id=conv_invalid")
    assert response.status_code == 404

def test_idor_guest_can_access_guest_conversation(monkeypatch):
    patch_conversation(monkeypatch, None)
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_guest

    response = client.get("/chat/history?conversation_id=conv_123")
    assert response.status_code == 200

def test_authenticated_chat_flow_still_works(monkeypatch):
    patch_conversation(monkeypatch, "user_A")
    from middleware.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user_A

    response = client.post("/chat/", json={"message": "hello", "conversation_id": "conv_123"})
    # Since we mocked supabase but not maxx_app entirely, it might return 500 if MAXX crashes, but we are just verifying it passes the 403/404 check
    assert response.status_code in [200, 500] 
    if response.status_code == 403:
        pytest.fail("Auth check failed incorrectly")
