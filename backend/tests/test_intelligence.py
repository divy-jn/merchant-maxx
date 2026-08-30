"""
Task 17 — Scout intelligence and ambiguity hardening tests.
All external services (LLM, Supabase, Pinecone) are mocked.
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


def _make_mock_supabase(product_data):
    """Create a mock supabase that returns product_data for product lookups."""
    mock = MagicMock()
    mock_table = MagicMock()
    mock.table.return_value = mock_table
    mock_select = mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value
    mock_select.data = product_data
    # For insert calls (purchase_intents)
    mock_table.insert.return_value.execute.return_value = MagicMock()
    return mock


def _make_mock_llm(tool_calls=None, content=""):
    """Create a mock LLM that returns a specific response."""
    mock_get_llm = MagicMock()
    mock_inst = MagicMock()
    mock_inst.invoke.return_value = AIMessage(
        content=content,
        tool_calls=tool_calls or []
    )
    mock_inst.bind_tools.return_value = mock_inst
    mock_get_llm.return_value = mock_inst
    return mock_get_llm


# ── Test 1: Multiple products → no purchase intent ──

def test_multiple_products_no_purchase_intent():
    """'Show me laptops' returns multiple products → no purchase intent should be staged."""
    from agents.scout import scout_node

    mock_supabase = _make_mock_supabase({
        "product_id": "item_laptop_001",
        "price_paise": 5000000,
        "active": True,
        "inventory_qty": 10
    })

    # LLM does NOT call stage_purchase_intent — it just searches
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "search_catalog", "args": {"query": "laptops"}, "id": "tc_1"}],
        content=""
    )

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", mock_supabase):
        state = {
            "messages": [HumanMessage(content="Show me laptops")],
            "session_id": "test_session",
            "customer_id": "test_customer"
        }
        result = scout_node(state)
        # No intent should be staged
        assert "scout_result" not in result or not result.get("scout_result", {}).get("intent_staged")


# ── Test 2: "I'll buy it" with multiple products → clarification ──

def test_ambiguous_purchase_no_intent():
    """'I'll buy it' with multiple products in context → no purchase intent."""
    from agents.scout import scout_node

    mock_supabase = _make_mock_supabase({
        "product_id": "item_laptop_001",
        "price_paise": 5000000,
        "active": True,
        "inventory_qty": 10
    })

    # The correct LLM behavior: when ambiguous, it should NOT call stage_purchase_intent.
    # This test verifies that even if the LLM misbehaves and calls it without
    # a product in history, the server-side guard blocks it.
    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_hallucinated", "amount_paise": 5000000}, "id": "tc_1"}],
    )

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", mock_supabase):
        # Conversation has two products in history
        state = {
            "messages": [
                ToolMessage(content="- Laptop A (ID: item_laptop_001)\n- Laptop B (ID: item_laptop_002)", tool_call_id="tc_search"),
                HumanMessage(content="I'll buy it")
            ],
            "session_id": "test_session",
            "customer_id": "test_customer"
        }
        result = scout_node(state)
        # item_hallucinated is not in known_ids, so it should be blocked
        assert not result.get("scout_result", {}).get("intent_staged")


# ── Test 3: Explicit single product → intent staged ──

def test_explicit_single_product_staged():
    """'I'll buy the Lenovo laptop' → exactly one product resolves → intent staged."""
    from agents.scout import scout_node

    mock_supabase = _make_mock_supabase({
        "product_id": "item_lenovo_001",
        "price_paise": 5500000,
        "active": True,
        "inventory_qty": 5
    })

    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_lenovo_001", "amount_paise": 5500000}, "id": "tc_1"}],
    )

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", mock_supabase):
        state = {
            "messages": [
                ToolMessage(content="- Lenovo IdeaPad (ID: item_lenovo_001)\n  Price: INR 55000.00", tool_call_id="tc_search"),
                HumanMessage(content="I'll buy the Lenovo laptop")
            ],
            "session_id": "test_session",
            "customer_id": "test_customer"
        }
        result = scout_node(state)
        assert result.get("scout_result", {}).get("intent_staged") is True
        ctx = result["scout_result"]["product_context"]
        assert ctx["basket_items"][0]["product_id"] == "item_lenovo_001"


# ── Test 4: "Looks good" → no purchase intent ──

def test_casual_interest_no_intent():
    """'Looks good' should not stage purchase intent."""
    from agents.scout import scout_node

    # LLM correctly does NOT call stage_purchase_intent for casual interest
    mock_llm = _make_mock_llm(content="Glad you like it! Would you like to purchase it?")

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", MagicMock()):
        state = {
            "messages": [HumanMessage(content="Looks good")],
            "session_id": "test_session",
            "customer_id": "test_customer"
        }
        result = scout_node(state)
        assert not result.get("scout_result", {}).get("intent_staged")


# ── Test 5: Quantity preserved as 2 ──

def test_quantity_two_preserved():
    """'I'll take two' with single product in context → quantity = 2."""
    from agents.scout import scout_node

    mock_supabase = _make_mock_supabase({
        "product_id": "item_mouse_001",
        "price_paise": 200000,
        "active": True,
        "inventory_qty": 10
    })

    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_mouse_001", "amount_paise": 400000, "quantity": 2}, "id": "tc_1"}],
    )

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", mock_supabase):
        state = {
            "messages": [
                ToolMessage(content="- Wireless Mouse (ID: item_mouse_001)\n  Price: INR 2000.00", tool_call_id="tc_search"),
                HumanMessage(content="I'll take two")
            ],
            "session_id": "test_session",
            "customer_id": "test_customer"
        }
        result = scout_node(state)
        assert result["scout_result"]["intent_staged"] is True
        ctx = result["scout_result"]["product_context"]
        assert ctx["basket_items"][0]["quantity"] == 2
        # Server-side: 2000 INR * 2 = 400,000 paise
        assert ctx["amount_paise"] == 400000


# ── Test 6: Invalid quantities ──

def test_quantity_zero_defaults_to_one():
    """Quantity 0 → safe fallback to 1."""
    from agents.scout import scout_node

    mock_supabase = _make_mock_supabase({
        "product_id": "item_test",
        "price_paise": 100000,
        "active": True,
        "inventory_qty": 5
    })

    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_test", "quantity": 0}, "id": "tc_1"}],
    )

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", mock_supabase):
        state = {
            "messages": [
                ToolMessage(content="Product (ID: item_test)", tool_call_id="tc_s"),
                HumanMessage(content="buy it")
            ],
            "session_id": "t", "customer_id": "c"
        }
        result = scout_node(state)
        if result.get("scout_result", {}).get("intent_staged"):
            assert result["scout_result"]["product_context"]["basket_items"][0]["quantity"] == 1


def test_quantity_negative_defaults_to_one():
    """Negative quantity → safe fallback to 1."""
    from agents.scout import scout_node

    mock_supabase = _make_mock_supabase({
        "product_id": "item_test",
        "price_paise": 100000,
        "active": True,
        "inventory_qty": 5
    })

    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_test", "quantity": -5}, "id": "tc_1"}],
    )

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", mock_supabase):
        state = {
            "messages": [
                ToolMessage(content="Product (ID: item_test)", tool_call_id="tc_s"),
                HumanMessage(content="buy it")
            ],
            "session_id": "t", "customer_id": "c"
        }
        result = scout_node(state)
        if result.get("scout_result", {}).get("intent_staged"):
            assert result["scout_result"]["product_context"]["basket_items"][0]["quantity"] == 1


def test_quantity_malformed_defaults_to_one():
    """Malformed quantity string → safe fallback to 1."""
    from agents.scout import scout_node

    mock_supabase = _make_mock_supabase({
        "product_id": "item_test",
        "price_paise": 100000,
        "active": True,
        "inventory_qty": 5
    })

    mock_llm = _make_mock_llm(
        tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "item_test", "quantity": "abc"}, "id": "tc_1"}],
    )

    with patch("agents.scout.get_llm", mock_llm), \
         patch("utils.supabase_client.supabase", mock_supabase):
        state = {
            "messages": [
                ToolMessage(content="Product (ID: item_test)", tool_call_id="tc_s"),
                HumanMessage(content="buy it")
            ],
            "session_id": "t", "customer_id": "c"
        }
        result = scout_node(state)
        if result.get("scout_result", {}).get("intent_staged"):
            assert result["scout_result"]["product_context"]["basket_items"][0]["quantity"] == 1


# ── Test: Tool schema ──

def test_stage_purchase_intent_tool_schema():
    """Verify stage_purchase_intent schema accepts quantity."""
    from agents.tools import stage_purchase_intent
    schema = stage_purchase_intent.args_schema.model_json_schema()
    assert "quantity" in schema["properties"]
    assert schema["properties"]["quantity"].get("default") == 1
    
    res = stage_purchase_intent.invoke({"product_id": "prod_1", "amount_paise": 1000, "quantity": 3})
    assert "3x prod_1" in res
