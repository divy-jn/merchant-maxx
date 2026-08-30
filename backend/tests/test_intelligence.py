import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

def test_scout_quantity_parsing():
    """Verify that Scout parses quantity and calculates amount correctly."""
    from agents.scout import scout_node
    
    with patch("agents.scout.get_llm") as mock_get_llm, \
         patch("utils.supabase_client.supabase") as mock_supabase:
         
        # Mock product fetch
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_select = mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value
        mock_select.data = {
            "product_id": "prod_laptop_001",
            "price_paise": 5000000,  # 50,000 INR
            "active": True,
            "inventory_qty": 10
        }
        
        # Mock LLM to return tool call with quantity 2
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(
            content="", 
            tool_calls=[{"name": "stage_purchase_intent", "args": {"product_id": "prod_laptop_001", "quantity": 2}, "id": "tc_1"}]
        )
        mock_inst.bind_tools.return_value = mock_inst
        mock_get_llm.return_value = mock_inst

        state = {
            "messages": [HumanMessage(content="I'll take two of those laptops")],
            "session_id": "test_session",
            "customer_id": "test_customer"
        }
        
        new_state = scout_node(state)
        
        # Verify context
        ctx = new_state["scout_result"]["product_context"]
        assert ctx["basket_items"][0]["quantity"] == 2
        # Price should be 50,000 * 2 = 100,000 INR = 10,000,000 paise
        assert ctx["amount_paise"] == 10000000
        assert "2x" in ctx["intent_description"]

def test_stage_purchase_intent_tool_schema():
    """Verify stage_purchase_intent schema accepts quantity."""
    from agents.tools import stage_purchase_intent
    schema = stage_purchase_intent.args_schema.model_json_schema()
    assert "quantity" in schema["properties"]
    assert schema["properties"]["quantity"].get("default") == 1
    
    # Test the tool directly
    res = stage_purchase_intent.invoke({"product_id": "prod_1", "amount_paise": 1000, "quantity": 3})
    assert "3x prod_1" in res
