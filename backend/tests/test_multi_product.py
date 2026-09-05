import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolCall, SystemMessage
from agents.scout import scout_node
from agents.maxx import maxx_app

@pytest.fixture
def mock_db():
    with patch("utils.supabase_client.supabase") as mock_supa:
        class MockResult:
            def __init__(self, data):
                self.data = data

        class MockQuery:
            def __init__(self, table):
                self.table = table
                self._product_id = "unknown"
                
            def select(self, *args, **kwargs):
                return self
                
            def eq(self, col, val):
                if col == "product_id":
                    self._product_id = val
                return self
                
            def is_(self, *args, **kwargs): return self
            def in_(self, *args, **kwargs): return self
            def neq(self, *args, **kwargs): return self
            def maybe_single(self): return self
            def limit(self, *args, **kwargs): return self
            
            def execute(self):
                if self.table == "products":
                    if self._product_id == "item_lenovo":
                        return MockResult({"product_id": "item_lenovo", "price_paise": 5000000, "active": True, "inventory_qty": 10})
                    elif self._product_id == "item_mouse":
                        return MockResult({"product_id": "item_mouse", "price_paise": 100000, "active": True, "inventory_qty": 50})
                    elif self._product_id == "item_keyboard":
                        return MockResult({"product_id": "item_keyboard", "price_paise": 200000, "active": True, "inventory_qty": 20})
                    else:
                        return MockResult(None)
                return MockResult(None)
                
            def insert(self, *args, **kwargs):
                return self
                
            def update(self, *args, **kwargs):
                return self

        def mock_table(table_name):
            return MockQuery(table_name)

        mock_supa.table.side_effect = mock_table
        yield mock_supa

def create_scout_mock(tool_calls):
    """Creates a mock LLM response with the specified tool calls"""
    with patch("agents.scout.get_llm") as mock_llm:
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(content="", tool_calls=tool_calls)
        mock_llm.return_value.bind_tools.return_value = mock_inst
        
        # Also bypass the known_ids check for deterministic testing
        with patch("agents.scout._extract_product_ids_from_history", return_value=set()):
            yield mock_inst

def test_add_second_product(mock_db):
    """Adding a second product appends instead of overwriting"""
    tc = [{"name": "stage_purchase_intent", "args": {"product_id": "item_mouse", "quantity": 1}, "id": "call_2"}]
    
    with patch("agents.scout.get_llm") as mock_llm, \
         patch("agents.scout._extract_product_ids_from_history", return_value={"item_mouse"}):
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(content="", tool_calls=tc)
        mock_llm.return_value.bind_tools.return_value = mock_inst

        state = {
            "messages": [SystemMessage(content="SYS"), HumanMessage(content="Add a mouse")],
            "purchase_context": {
                "purchase_intent_id": "pi_123",
                "basket_items": [{"product_id": "item_lenovo", "quantity": 1}]
            }
        }
        
        res = scout_node(state)
        ctx = res["scout_result"]["product_context"]
        basket = ctx["basket_items"]
        
        assert len(basket) == 2
        assert basket[0]["product_id"] == "item_lenovo"
        assert basket[1]["product_id"] == "item_mouse"
        assert ctx["amount_paise"] == 5100000  # 50k + 1k

def test_increase_quantity(mock_db):
    """Increasing quantity updates the existing entry"""
    tc = [{"name": "stage_purchase_intent", "args": {"product_id": "item_lenovo", "quantity": 2}, "id": "call_1"}]
    
    with patch("agents.scout.get_llm") as mock_llm, \
         patch("agents.scout._extract_product_ids_from_history", return_value={"item_lenovo"}):
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(content="", tool_calls=tc)
        mock_llm.return_value.bind_tools.return_value = mock_inst

        state = {
            "messages": [SystemMessage(content="SYS"), HumanMessage(content="Make that two lenovos")],
            "purchase_context": {
                "purchase_intent_id": "pi_123",
                "basket_items": [{"product_id": "item_lenovo", "quantity": 1}]
            }
        }
        
        res = scout_node(state)
        ctx = res["scout_result"]["product_context"]
        basket = ctx["basket_items"]
        
        assert len(basket) == 1
        assert basket[0]["product_id"] == "item_lenovo"
        assert basket[0]["quantity"] == 2
        assert ctx["amount_paise"] == 10000000  # 50k * 2

def test_remove_item(mock_db):
    """Removing an item (quantity=0) works"""
    tc = [{"name": "stage_purchase_intent", "args": {"product_id": "item_mouse", "quantity": 0}, "id": "call_1"}]
    
    with patch("agents.scout.get_llm") as mock_llm, \
         patch("agents.scout._extract_product_ids_from_history", return_value={"item_mouse"}):
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(content="", tool_calls=tc)
        mock_llm.return_value.bind_tools.return_value = mock_inst

        state = {
            "messages": [SystemMessage(content="SYS"), HumanMessage(content="Remove the mouse")],
            "purchase_context": {
                "purchase_intent_id": "pi_123",
                "basket_items": [{"product_id": "item_lenovo", "quantity": 1}, {"product_id": "item_mouse", "quantity": 1}]
            }
        }
        
        res = scout_node(state)
        ctx = res["scout_result"]["product_context"]
        basket = ctx["basket_items"]
        
        assert len(basket) == 1
        assert basket[0]["product_id"] == "item_lenovo"
        assert ctx["amount_paise"] == 5000000

def test_unknown_product_rejected(mock_db):
    """Unknown product rejection"""
    tc = [{"name": "stage_purchase_intent", "args": {"product_id": "item_fake", "quantity": 1}, "id": "call_1"}]
    
    with patch("agents.scout.get_llm") as mock_llm, \
         patch("agents.scout._extract_product_ids_from_history", return_value={"item_fake"}):
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(content="", tool_calls=tc)
        mock_llm.return_value.bind_tools.return_value = mock_inst

        state = {
            "messages": [SystemMessage(content="SYS"), HumanMessage(content="I want a fake item")],
        }
        
        res = scout_node(state)
        # Should NOT stage intent because product is not valid
        assert "scout_result" not in res

def test_multiple_products_one_turn(mock_db):
    """Lenovo and a mouse in one turn"""
    tc = [
        {"name": "stage_purchase_intent", "args": {"product_id": "item_lenovo", "quantity": 1}, "id": "call_1"},
        {"name": "stage_purchase_intent", "args": {"product_id": "item_mouse", "quantity": 1}, "id": "call_2"}
    ]
    
    with patch("agents.scout.get_llm") as mock_llm, \
         patch("agents.scout._extract_product_ids_from_history", return_value={"item_lenovo", "item_mouse"}):
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(content="", tool_calls=tc)
        mock_llm.return_value.bind_tools.return_value = mock_inst

        state = {
            "messages": [SystemMessage(content="SYS"), HumanMessage(content="I want the Lenovo and a mouse")],
        }
        
        res = scout_node(state)
        ctx = res.get("scout_result", {}).get("product_context", {})
        basket = ctx.get("basket_items", [])
        
        print("BASKET IS:", basket)
        assert len(basket) == 2
        assert basket[0]["product_id"] == "item_lenovo"
        assert basket[1]["product_id"] == "item_mouse"
        assert ctx["amount_paise"] == 5100000

def test_those_n_collapses_to_quantity(mock_db):
    """'ok give those 2' must NOT add two different products.
    The server-side guard collapses multiple qty=1 calls into one call with qty=N."""
    tc = [
        {"name": "stage_purchase_intent", "args": {"product_id": "item_lenovo", "quantity": 1}, "id": "call_1"},
        {"name": "stage_purchase_intent", "args": {"product_id": "item_mouse", "quantity": 1}, "id": "call_2"}
    ]

    with patch("agents.scout.get_llm") as mock_llm, \
         patch("agents.scout._extract_product_ids_from_history", return_value={"item_lenovo", "item_mouse"}):
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(content="", tool_calls=tc)
        mock_llm.return_value.bind_tools.return_value = mock_inst

        state = {
            "messages": [SystemMessage(content="SYS"), HumanMessage(content="ok give those 2")],
        }

        res = scout_node(state)
        ctx = res.get("scout_result", {}).get("product_context", {})
        basket = ctx.get("basket_items", [])

        # Guard must collapse into 1 item with qty=2
        assert len(basket) == 1, f"Expected 1 item but got {len(basket)}: {basket}"
        assert basket[0]["quantity"] == 2, f"Expected qty=2 but got {basket[0]['quantity']}"
