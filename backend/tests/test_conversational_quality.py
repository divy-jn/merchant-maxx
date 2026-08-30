"""
Task 18 — Conversational Evaluation Matrix
Evaluates ecommerce conversation handling, ambiguity, context retention, and multi-turn stability.
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

def _make_mock_llm(tool_calls=None, content=""):
    mock_get_llm = MagicMock()
    mock_inst = MagicMock()
    mock_inst.invoke.return_value = AIMessage(
        content=content,
        tool_calls=tool_calls or []
    )
    mock_inst.bind_tools.return_value = mock_inst
    mock_get_llm.return_value = mock_inst
    return mock_get_llm

def _make_mock_supabase(product_data):
    mock = MagicMock()
    mock_table = MagicMock()
    mock.table.return_value = mock_table
    mock_select = mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value
    mock_select.data = product_data
    mock_table.insert.return_value.execute.return_value = MagicMock()
    return mock


# ── TEST 1: Product Discovery ──
def test_product_discovery():
    from agents.scout import scout_node
    mock_llm = _make_mock_llm(tool_calls=[{"name": "search_catalog", "args": {"query": "laptops"}, "id": "tc_1"}])
    with patch("agents.scout.get_llm", mock_llm):
        state = {"messages": [HumanMessage(content="Show me laptops")], "session_id": "t1"}
        result = scout_node(state)
        # Should not stage intent
        assert not result.get("scout_result", {}).get("intent_staged")


# ── TEST 2: Product Details ──
def test_product_details():
    from agents.scout import scout_node
    mock_llm = _make_mock_llm(tool_calls=[{"name": "get_product_details", "args": {"product_id": "item_2"}, "id": "tc_1"}])
    with patch("agents.scout.get_llm", mock_llm):
        state = {
            "messages": [
                ToolMessage(content="1. Laptop A (ID: item_1)\n2. Laptop B (ID: item_2)", tool_call_id="tc_search"),
                HumanMessage(content="What's the price of the second one?")
            ],
            "session_id": "t2"
        }
        result = scout_node(state)
        assert not result.get("scout_result", {}).get("intent_staged")


# ── TEST 3: Comparison ──
def test_comparison():
    from agents.scout import scout_node
    # In reality the model might call get_product_details multiple times or compare based on search result.
    # We just ensure it does NOT stage intent.
    mock_llm = _make_mock_llm(content="Laptop A is faster but Laptop B is lighter.")
    with patch("agents.scout.get_llm", mock_llm):
        state = {
            "messages": [
                ToolMessage(content="1. Laptop A (ID: item_1)\n2. Laptop B (ID: item_2)", tool_call_id="tc_search"),
                HumanMessage(content="Compare the first two laptops")
            ],
            "session_id": "t3"
        }
        result = scout_node(state)
        assert not result.get("scout_result", {}).get("intent_staged")


# ── TEST 4: Explicit Selection ──
def test_explicit_selection():
    from agents.scout import scout_node
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_lenovo"}, "id": "tc_1"}]
    )
    mock_db = _make_mock_supabase({"product_id": "item_lenovo", "price_paise": 5000000, "active": True, "inventory_qty": 5})
    with patch("agents.scout.get_llm", mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                ToolMessage(content="Lenovo Laptop (ID: item_lenovo)", tool_call_id="tc_search"),
                HumanMessage(content="I'll take the Lenovo one")
            ],
            "session_id": "t4"
        }
        result = scout_node(state)
        assert result.get("scout_result", {}).get("intent_staged")
        assert result["scout_result"]["product_context"]["basket_items"][0]["product_id"] == "item_lenovo"
        assert result["scout_result"]["product_context"]["basket_items"][0]["quantity"] == 1


# ── TEST 5: Quantity ──
def test_quantity():
    from agents.scout import scout_node
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_lenovo", "quantity": 2}, "id": "tc_1"}]
    )
    mock_db = _make_mock_supabase({"product_id": "item_lenovo", "price_paise": 5000000, "active": True, "inventory_qty": 5})
    with patch("agents.scout.get_llm", mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                ToolMessage(content="Lenovo Laptop (ID: item_lenovo)", tool_call_id="tc_search"),
                HumanMessage(content="I'll take two of those")
            ],
            "session_id": "t5"
        }
        result = scout_node(state)
        ctx = result["scout_result"]["product_context"]
        assert ctx["basket_items"][0]["quantity"] == 2
        assert ctx["amount_paise"] == 10000000  # 50k * 2


# ── TEST 6: Casual Interest ──
def test_casual_interest():
    from agents.scout import scout_node
    # LLM should not emit stage_purchase_intent
    mock_llm = _make_mock_llm(content="Glad you like it! Would you like to buy it?")
    with patch("agents.scout.get_llm", mock_llm):
        state = {
            "messages": [
                ToolMessage(content="Lenovo Laptop (ID: item_lenovo)", tool_call_id="tc_search"),
                HumanMessage(content="That looks good")
            ],
            "session_id": "t6"
        }
        result = scout_node(state)
        assert not result.get("scout_result", {}).get("intent_staged")


# ── TEST 7: Ambiguous Purchase ──
def test_ambiguous_purchase():
    from agents.scout import scout_node
    # LLM might hallucinate a product id if it guesses. We test the guard blocks it.
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_fake"}, "id": "tc_1"}]
    )
    mock_db = _make_mock_supabase({"product_id": "item_fake", "price_paise": 500, "active": True, "inventory_qty": 5})
    with patch("agents.scout.get_llm", mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                ToolMessage(content="Laptop A (ID: item_1)\nLaptop B (ID: item_2)", tool_call_id="tc_search"),
                HumanMessage(content="I'll buy it")
            ],
            "session_id": "t7"
        }
        result = scout_node(state)
        # item_fake is not in context history [item_1, item_2], so it should be blocked
        assert not result.get("scout_result", {}).get("intent_staged")


# ── TEST 8: Explicit After Ambiguity ──
def test_explicit_after_ambiguity():
    from agents.scout import scout_node
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_2"}, "id": "tc_1"}]
    )
    mock_db = _make_mock_supabase({"product_id": "item_2", "price_paise": 500, "active": True, "inventory_qty": 5})
    with patch("agents.scout.get_llm", mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                ToolMessage(content="Laptop A (ID: item_1)\nLaptop B (ID: item_2)", tool_call_id="tc_search"),
                HumanMessage(content="I'll buy it"),
                AIMessage(content="Which one?"),
                HumanMessage(content="I'll buy the second one")
            ],
            "session_id": "t8"
        }
        result = scout_node(state)
        assert result.get("scout_result", {}).get("intent_staged")
        assert result["scout_result"]["product_context"]["basket_items"][0]["product_id"] == "item_2"


# ── TEST 9: Context Correction ──
def test_context_correction():
    from agents.scout import scout_node
    # First intent was Lenovo. User changes mind. LLM should stage HP.
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_hp"}, "id": "tc_1"}]
    )
    mock_db = _make_mock_supabase({"product_id": "item_hp", "price_paise": 600, "active": True, "inventory_qty": 5})
    with patch("agents.scout.get_llm", mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                ToolMessage(content="Lenovo (ID: item_lenovo)\nHP (ID: item_hp)", tool_call_id="tc_s"),
                HumanMessage(content="I want the Lenovo one"),
                AIMessage(content="Great, staged.", tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_lenovo"}, "id": "tc_0"}]),
                HumanMessage(content="Actually, give me the HP one")
            ],
            "session_id": "t9"
        }
        result = scout_node(state)
        assert result.get("scout_result", {}).get("intent_staged")
        assert result["scout_result"]["product_context"]["basket_items"][0]["product_id"] == "item_hp"


# ── TEST 10: Multi-product Basket (Now Supported) ──
def test_multi_product_basket_supported():
    from agents.scout import scout_node
    # Our architecture now supports multiple products in the basket.
    mock_llm = _make_mock_llm(
        tool_calls=[
            {"name": "stage_purchase_intent", "args": {"product_id": "item_laptop"}, "id": "tc_1"},
            {"name": "stage_purchase_intent", "args": {"product_id": "item_mouse"}, "id": "tc_2"}
        ]
    )
    
    class MockResult:
        def __init__(self, data):
            self.data = data
            
    class MockQuery:
        def __init__(self, *args, **kwargs):
            self._pid = None
        def select(self, *args, **kwargs): return self
        def eq(self, col, val):
            if col == "product_id": self._pid = val
            return self
        def maybe_single(self): return self
        def execute(self):
            if self._pid == "item_laptop": return MockResult({"product_id": "item_laptop", "price_paise": 500, "active": True, "inventory_qty": 5})
            if self._pid == "item_mouse": return MockResult({"product_id": "item_mouse", "price_paise": 100, "active": True, "inventory_qty": 5})
            return MockResult(None)
        def is_(self, *args, **kwargs): return self
        def in_(self, *args, **kwargs): return self
        def neq(self, *args, **kwargs): return self
        def insert(self, *args, **kwargs): return self
        def update(self, *args, **kwargs): return self
            
    mock_db = MagicMock()
    mock_db.table.return_value = MockQuery()
    
    with patch("agents.scout.get_llm", mock_llm), patch("utils.supabase_client.supabase", mock_db):
        state = {
            "messages": [
                ToolMessage(content="Laptop (ID: item_laptop)\nMouse (ID: item_mouse)", tool_call_id="tc_s"),
                HumanMessage(content="I want the laptop and mouse")
            ],
            "session_id": "t10"
        }
        result = scout_node(state)
        # It should process both the laptop and mouse.
        ctx = result["scout_result"]["product_context"]
        assert len(ctx["basket_items"]) == 2
        assert ctx["basket_items"][0]["product_id"] == "item_laptop"
        assert ctx["basket_items"][1]["product_id"] == "item_mouse"

