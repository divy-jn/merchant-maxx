import pytest
from unittest.mock import patch, MagicMock
from agents.tools import create_razorpay_order, check_payment_status
from services.payment_resolution import resolve_payment_status
from services.refund_service import initiate_refund, check_refund_status

class FakeResponse:
    def __init__(self, data):
        self.data = data

class FakeQuery:
    def __init__(self, table_name, data_store):
        self.table_name = table_name
        self.data_store = data_store
        self._is_single = False
        
    def select(self, *args, **kwargs): return self
    def insert(self, *args, **kwargs): 
        if self.table_name == "orders" and self.data_store.get("raise_order_insert"):
            raise Exception("DB Timeout")
        if self.table_name == "refunds" and self.data_store.get("raise_idempotency"):
            class DBException(Exception):
                pass
            err = DBException("duplicate key value violates unique constraint uq_refund_idempotency")
            err.code = "23505"
            raise err
        return self
    def update(self, *args, **kwargs): return self
    def upsert(self, *args, **kwargs): return self
    def delete(self, *args, **kwargs): return self
    def eq(self, *args, **kwargs): return self
    def neq(self, *args, **kwargs): return self
    def in_(self, *args, **kwargs): return self
    def limit(self, *args, **kwargs): return self
    def maybe_single(self, *args, **kwargs): 
        self._is_single = True
        return self
        
    def execute(self, *args, **kwargs):
        if self.table_name in self.data_store:
            val = self.data_store[self.table_name]
            if isinstance(val, list):
                if self._is_single:
                    return FakeResponse(val[0] if val else None)
                return FakeResponse(val)
            else:
                if self._is_single:
                    return FakeResponse(val)
                return FakeResponse([val] if val else [])
        return FakeResponse(None)

class FakeRPC:
    def __init__(self, rpc_res):
        self.rpc_res = rpc_res
    def execute(self):
        return FakeResponse(self.rpc_res)

class FakeSupabase:
    def __init__(self):
        self.data_store = {}
        self.rpc_res = {}
    def table(self, name):
        return FakeQuery(name, self.data_store)
    def rpc(self, name, params=None):
        return FakeRPC(self.rpc_res)

@pytest.fixture
def fake_db():
    db = FakeSupabase()
    with patch("services.payment_resolution.supabase", db), \
         patch("services.refund_service.supabase", db), \
         patch("agents.tools.supabase", db):
        yield db

@pytest.fixture
def mock_rzp():
    with patch("razorpay_service.client.rzp") as mock_rzp_client:
        yield mock_rzp_client
        
@pytest.fixture
def mock_orders():
    with patch("razorpay_service.orders.create_order") as mock_create_order:
        mock_create_order.return_value = {"id": "order_rzp_12345"}
        yield mock_create_order

def test_phase8_1_create_razorpay_order_fails_locally(fake_db, mock_orders):
    fake_db.data_store["purchase_intents"] = {
        "purchase_intent_id": "pi_123", "purchase_state": "USER_CONFIRMED",
        "user_confirmed": True, "amount_paise": 1000, "confirmed_amount_paise": 1000,
        "basket": [{"product_id": "p_1", "quantity": 1}],
        "confirmed_basket": [{"product_id": "p_1", "quantity": 1}],
        "conversation_id": "sess_1"
    }
    fake_db.data_store["products"] = {
        "product_id": "p_1", "active": True, "inventory_qty": 10, "price_paise": 1000
    }
    fake_db.data_store["orders"] = None
    fake_db.data_store["raise_order_insert"] = True
    
    state = {"purchase_context": {"purchase_intent_id": "pi_123"}, "session_id": "sess_1"}
    result = create_razorpay_order.invoke({"state": state})
    assert "System will recover automatically" in result

def test_phase8_4_retry_after_persistence_failure(fake_db, mock_orders):
    fake_db.data_store["purchase_intents"] = {
        "purchase_intent_id": "pi_123", "purchase_state": "PAYMENT_PENDING",
        "user_confirmed": True, "amount_paise": 1000, "razorpay_order_id": "order_rzp_12345",
        "basket": [{"product_id": "p_1", "quantity": 1}], "conversation_id": "sess_1"
    }
    fake_db.data_store["orders"] = None
    
    state = {"purchase_context": {"purchase_intent_id": "pi_123"}, "session_id": "sess_1"}
    result = create_razorpay_order.invoke({"state": state})
    assert "Razorpay Order already exists" in result

def test_phase5_webhook_and_reconciliation_equivalence(fake_db):
    fake_db.data_store["entity_mapping"] = [{"synthetic_id": "ord_123"}]
    fake_db.data_store["orders"] = {"order_id": "ord_123", "purchase_intent_id": "pi_123"}
    fake_db.data_store["purchase_intents"] = {
        "purchase_intent_id": "pi_123", "purchase_state": "PAYMENT_PENDING", "amount_paise": 1000, "basket": []
    }
    fake_db.rpc_res = {"status": "success"}
    
    res = resolve_payment_status("rzp_order_123", "rzp_pay_123", 1000, "CAPTURED", "webhook")
    assert res["status"] == "ok"
    assert res["state"] == "PAYMENT_SUCCESS"
    assert res["fulfillment"] == "FULFILLED"
    
    fake_db.data_store["purchase_intents"]["purchase_state"] = "PAYMENT_SUCCESS"
    res2 = resolve_payment_status("rzp_order_123", "rzp_pay_123", 1000, "CAPTURED", "reconciliation")
    assert res2["status"] == "ok"
    # It either returns terminal/no-op or succeeds idempotently
    assert res2.get("reason") in ["terminal state", "no-op transition"] or res2.get("state") == "PAYMENT_SUCCESS"

def test_phase8_33_duplicate_refunds_prevented(fake_db, mock_rzp):
    fake_db.data_store["raise_idempotency"] = True
    fake_db.data_store["refunds"] = {
        "status": "REFUNDED", "refund_id": "ref_123", "razorpay_refund_id": "rzp_ref_123"
    }
    
    res = initiate_refund("pay_123", "rzp_pay_123", "ord_123", "cust_123", 1000)
    mock_rzp.payment.refund.assert_not_called()
    assert res["status"] == "REFUNDED"
    assert res["refund_id"] == "ref_123"

def test_phase4_fulfillment_failure_triggers_refund(fake_db, mock_rzp):
    fake_db.data_store["entity_mapping"] = [{"synthetic_id": "ord_123"}]
    fake_db.data_store["orders"] = {"order_id": "ord_123", "purchase_intent_id": "pi_123"}
    fake_db.data_store["purchase_intents"] = {
        "purchase_intent_id": "pi_123", "purchase_state": "PAYMENT_PENDING", "amount_paise": 1000, "basket": []
    }
    fake_db.data_store["refunds"] = []
    fake_db.data_store["payments"] = []
    fake_db.rpc_res = {"status": "insufficient_inventory"}
    mock_rzp.payment.refund.return_value = {"id": "rzp_ref_123"}
    
    res = resolve_payment_status("rzp_order_123", "rzp_pay_123", 1000, "CAPTURED")
    assert res["status"] == "ok"
    assert res["fulfillment"] == "UNFULFILLED"
    mock_rzp.payment.refund.assert_called_once()
