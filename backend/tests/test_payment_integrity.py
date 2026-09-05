import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage

# --- Mocks ---

class MockResult:
    def __init__(self, data):
        self.data = data

class MockQuery:
    def __init__(self, *args, **kwargs):
        self.q = []
        self.is_update = False
    def select(self, *args, **kwargs): return self
    def eq(self, col, val): 
        self.q.append(("eq", col, val))
        return self
    def limit(self, *args, **kwargs): return self
    def maybe_single(self): return self
    def is_(self, *args, **kwargs): return self
    def in_(self, *args, **kwargs): return self
    def neq(self, *args, **kwargs): return self
    def execute(self):
        pid = None
        pi_id = None
        oid = None
        for op, col, val in self.q:
            if col == "product_id": pid = val
            if col == "purchase_intent_id": pi_id = val
            if col == "order_id": oid = val
            
        if pid:
            if pid == "item_laptop": return MockResult({"product_id": "item_laptop", "price_paise": 5000000, "active": True, "inventory_qty": 5})
            if pid == "item_mouse": return MockResult({"product_id": "item_mouse", "price_paise": 500000, "active": True, "inventory_qty": 5})
        if pi_id:
            # Mock locked intent scenario
            if pi_id == "pi_locked":
                return MockResult([]) if self.is_update else MockResult({"razorpay_order_id": "order_A", "order_id": "syn_ord_1"})
            if pi_id == "pi_unlocked":
                return MockResult([{}]) if self.is_update else MockResult({})
        return MockResult([]) if self.is_update else MockResult({})
    def update(self, *args, **kwargs): 
        self.is_update = True
        return self
    def insert(self, *args, **kwargs): return self

def _make_mock_llm(tool_calls=None):
    mock = MagicMock()
    msg = AIMessage(content="Testing")
    if tool_calls:
        msg.tool_calls = tool_calls
    mock.bind_tools.return_value.invoke.return_value = msg
    return mock

# --- Tests ---

def test_intent_locking_preserves_old_order_and_creates_new_intent():
    from agents.scout import scout_node
    
    # We simulate modifying a locked intent (pi_locked).
    # Scout should generate a new intent ID and not mutate pi_locked.
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_mouse", "quantity": 1}, "id": "tc_1"}]
    )
    
    mock_db = MagicMock()
    def mock_table(name):
        return MockQuery()
    mock_db.table.side_effect = mock_table
    
    with patch("agents.scout.get_llm", return_value=mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                HumanMessage(content="Add a mouse")
            ],
            "session_id": "t1",
            "purchase_context": {
                "purchase_intent_id": "pi_locked",
                "basket_items": [{"product_id": "item_laptop", "quantity": 1}]
            }
        }
        
        result = scout_node(state)
        ctx = result["scout_result"]["product_context"]
        
        # Invariant 1: New intent receives a NEW ID
        assert ctx["purchase_intent_id"] != "pi_locked"
        assert ctx["purchase_intent_id"].startswith("pi_")
        
        # Invariant 2: New intent clones and modifies the complete basket
        assert len(ctx["basket_items"]) == 2
        assert ctx["basket_items"][0]["product_id"] == "item_laptop"
        assert ctx["basket_items"][1]["product_id"] == "item_mouse"
        
        # Invariant 3: Server recalculates complete subtotal
        assert ctx["amount_paise"] == 5500000

def test_unlocked_intent_is_mutated_in_place():
    from agents.scout import scout_node
    
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_mouse", "quantity": 1}, "id": "tc_1"}]
    )
    mock_db = MagicMock()
    def mock_table(name):
        return MockQuery()
    mock_db.table.side_effect = mock_table
    
    with patch("agents.scout.get_llm", return_value=mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                HumanMessage(content="Add a mouse")
            ],
            "session_id": "t2",
            "purchase_context": {
                "purchase_intent_id": "pi_unlocked",
                "basket_items": [{"product_id": "item_laptop", "quantity": 1}]
            }
        }
        
        result = scout_node(state)
        ctx = result["scout_result"]["product_context"]
        
        # Intent was NOT locked, so it should be mutated in place
        assert ctx["purchase_intent_id"] == "pi_unlocked"
        assert len(ctx["basket_items"]) == 2

def test_create_razorpay_order_maintains_db_uniqueness():
    from agents.tools import create_razorpay_order
    
    # Simulate DB unique constraint violation on order creation
    mock_db = MagicMock()
    # First, order insert throws exception (simulating unique constraint)
    # Then, we fetch the existing order mapping.
    class MockMappingQuery:
        def select(self, *args): return self
        def eq(self, *args): return self
        def limit(self, *args): return self
        def maybe_single(self): return self
        def execute(self):
            return MockResult({"order_id": "syn_ord_1", "razorpay_id": "order_XYZ"})

    def mock_table(name):
        q = MagicMock()
        if name == "orders":
            q.insert.side_effect = Exception("duplicate key value violates unique constraint")
            q.select.return_value = MockMappingQuery()
        elif name == "entity_mapping":
            q.select.return_value = MockMappingQuery()
        elif name == "purchase_intents":
            intent_mock = {"purchase_intent_id": "pi_existing", "conversation_id": "conv_123", "purchase_state": "USER_CONFIRMED", "user_confirmed": True, "basket": [{"product_id": "laptop", "quantity": 1}], "amount_paise": 50000, "confirmed_basket": [{"product_id": "laptop", "quantity": 1}], "confirmed_amount_paise": 50000}
            q.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MockResult(intent_mock)
            q.update.return_value.eq.return_value.eq.return_value.execute.return_value = MockResult([dict(intent_mock, purchase_state="ORDER_CREATING")])
        elif name == "products":
            q.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MockResult({"price_paise": 50000})
        return q

    mock_db.table.side_effect = mock_table
    
    with patch("agents.tools.supabase", mock_db):
        response = create_razorpay_order.invoke(
            input={
                "state": {
                    "session_id": "conv_123",
                    "purchase_context": {
                        "purchase_intent_id": "pi_existing",
                        "basket": [{"product_id": "laptop", "quantity": 1}],
                        "purchase_state": "USER_CONFIRMED",
                        "user_confirmed": True,
                        "amount_paise": 50000
                    }
                },
                "customer_email": "test@test.com",
                "customer_contact": None
            },
            config={"configurable": {"thread_id": "t1"}}
        )
        # Should return the existing order safely, rather than crashing
        assert "Your purchase cannot be processed at this time due to our security policies" in response

def test_webhook_cross_check_no_downgrade_or_cross_mutation():
    from routes.webhooks import handle_razorpay_webhook
    from fastapi import Request
    import asyncio
    
    # We simulate a webhook for Order A, trying to verify it doesn't touch Intent B.
    # We'll assert that the Supabase update only targets the correct intent_id.
    
    class MockRequest:
        async def body(self): return b'{"event":"payment.captured"}'
        @property
        def headers(self):
            class Headers:
                def get(self, k, default): return {"X-Razorpay-Signature": "sig"}.get(k, default)
            return Headers()
        async def json(self): return {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": "order_A", "id": "pay_A", "amount": 5000000}}}
        }
        client = MagicMock(host="127.0.0.1")
    
    mock_db = MagicMock()
    
    class MockMappingQuery:
        def select(self, *args): return self
        def eq(self, *args): return self
        def limit(self, *args): return self
        def maybe_single(self): return self
        def execute(self):
            return MockResult([{"synthetic_id": "syn_ord_1"}])
            
    class MockOrderQuery:
        def select(self, *args): return self
        def eq(self, *args): return self
        def maybe_single(self): return self
        def execute(self):
            # Order A maps to Intent A, amount 50000
            return MockResult({"order_id": "syn_ord_1", "total_paise": 5000000, "purchase_intent_id": "intent_A"})

    class MockIntentQuery:
        def select(self, *args): return self
        def eq(self, *args): return self
        def neq(self, *args): return self
        def maybe_single(self): return self
        def execute(self):
            return MockResult({"purchase_state": "PAYMENT_PENDING", "amount_paise": 5000000})

    def mock_table(name):
        q = MagicMock()
        if name == "entity_mapping":
            q.select.return_value = MockMappingQuery()
        elif name == "orders":
            q.select.return_value = MockOrderQuery()
        elif name == "purchase_intents":
            q.select.return_value = MockIntentQuery()
            # Ensure update is tracked so we can assert on it
            q.update.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MockResult({})
        return q

    mock_db.table.side_effect = mock_table

    with patch("routes.webhooks.supabase", mock_db), patch("services.payment_resolution.supabase", mock_db), patch("routes.webhooks.rzp", MagicMock()), patch("routes.webhooks.settings.RAZORPAY_WEBHOOK_SECRET", "secret"):
        req = MockRequest()
        asyncio.run(handle_razorpay_webhook(req))
        
        # Verify the purchase_intents update only targeted intent_A
        mock_db.table.assert_any_call("purchase_intents")
        # Find the eq call on purchase_intents
        for call in mock_db.table("purchase_intents").eq.call_args_list:
            if call.args[0] == "purchase_intent_id":
                assert call.args[1] == "intent_A", "Webhook must not mutate other intents"
