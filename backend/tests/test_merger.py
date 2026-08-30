"""
Task 17 — Merger conflict and deterministic state tests.
"""
import pytest
from unittest.mock import patch, MagicMock
from agents.merger import merger_node
from agents.payment_state import can_transition, is_terminal


def test_scout_booster_same_product_merges():
    """Scout and Booster refer to the same product → merge normally."""
    state = {
        "purchase_state": "IDLE",
        "purchase_context": {},
        "scout_result": {
            "intent_staged": True,
            "product_context": {
                "purchase_intent_id": "pi_test",
                "basket_items": [{"product_id": "prod_001", "quantity": 1}],
                "amount_paise": 50000,
            }
        },
        "booster_result": {"status": "success", "recommendations_shown": False}
    }
    result = merger_node(state)
    # IDLE → PRODUCT_SELECTED, then booster success without recs → PURCHASE_PENDING
    assert result["purchase_state"] == "PURCHASE_PENDING"
    assert result["purchase_context"]["basket_items"][0]["product_id"] == "prod_001"


def test_booster_no_recommendation_continues():
    """Booster has no recommendation → continue normally to PURCHASE_PENDING."""
    state = {
        "purchase_state": "PRODUCT_SELECTED",
        "purchase_context": {"basket_items": [{"product_id": "prod_001"}]},
        "scout_result": {},
        "booster_result": {"status": "skipped", "reason": "missing_context"}
    }
    result = merger_node(state)
    assert result["purchase_state"] == "PURCHASE_PENDING"


def test_booster_failure_preserves_checkout():
    """Booster fails (429) → checkout remains available via PURCHASE_PENDING."""
    state = {
        "purchase_state": "PRODUCT_SELECTED",
        "purchase_context": {"basket_items": [{"product_id": "prod_001"}]},
        "scout_result": {},
        "booster_result": {"status": "unavailable"}
    }
    result = merger_node(state)
    assert result["purchase_state"] == "PURCHASE_PENDING"


def test_booster_conflicting_product_logged_and_ignored():
    """Scout and Booster contain different product IDs → Booster's product is ignored."""
    state = {
        "purchase_state": "PRODUCT_SELECTED",
        "purchase_context": {"basket_items": [{"product_id": "prod_001"}]},
        "scout_result": {},
        "booster_result": {
            "status": "success",
            "product_id": "prod_999",  # different from Scout's
            "recommendations_shown": True
        }
    }
    result = merger_node(state)
    # Merger should still process recommendation status, but not override product
    assert result["purchase_state"] == "RECOMMENDATION_SHOWN"
    # purchase_context should NOT be changed to prod_999
    ctx = result.get("purchase_context", state["purchase_context"])
    assert ctx["basket_items"][0]["product_id"] == "prod_001"


def test_payment_success_remains_terminal():
    """PAYMENT_SUCCESS followed by any state → state remains PAYMENT_SUCCESS."""
    state = {
        "purchase_state": "PAYMENT_SUCCESS",
        "scout_result": {"intent_staged": True, "product_context": {}},
        "booster_result": {"status": "unavailable"}
    }
    result = merger_node(state)
    assert result.get("purchase_state", "PAYMENT_SUCCESS") == "PAYMENT_SUCCESS"


def test_payment_success_is_terminal():
    """PAYMENT_SUCCESS is a terminal state with no outgoing transitions."""
    assert is_terminal("PAYMENT_SUCCESS")
    assert not can_transition("PAYMENT_SUCCESS", "PAYMENT_FAILED")
    assert not can_transition("PAYMENT_SUCCESS", "PAYMENT_PENDING")
    assert not can_transition("PAYMENT_SUCCESS", "IDLE")
    # Idempotent same-state is allowed
    assert can_transition("PAYMENT_SUCCESS", "PAYMENT_SUCCESS")
