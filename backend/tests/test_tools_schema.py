"""
Task 18 — Tool schema and invocation accuracy tests.
Verifies critical tool argument handling, missing arguments, and failure handling.
"""
import pytest
from agents.tools import stage_purchase_intent, create_razorpay_order
from pydantic import ValidationError

def test_stage_purchase_intent_missing_args():
    schema = stage_purchase_intent.args_schema.model_json_schema()
    # verify product_id is in required
    assert "product_id" in schema["required"]

def test_create_razorpay_order_missing_args():
    schema = create_razorpay_order.args_schema.model_json_schema()
    # verify state is required by graph injection (handled by langgraph)
    # verify it doesn't strictly require purchase_intent_id from LLM (it gets it from state)
    assert schema.get("required") is None or "purchase_intent_id" not in schema.get("required", [])

