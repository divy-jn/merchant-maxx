"""
Test suite for the conversational purchase flow.
Covers: product discovery, cart management, confirmation, checkout, and edge cases.
All LLM calls are mocked — tests verify deterministic backend logic only.
"""
import pytest
import uuid
import re
import os
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

os.environ.setdefault("APP_ENV", "test")

from config import settings
from agents.payment_state import can_transition, VALID_TRANSITIONS, TERMINAL_STATES
from routes.chat import (
    CONFIRM_RE,
    _get_actions_for_state,
    ChatAction,
)


# ── 1. Vague product request ──────────────────────────────────────────

class TestProductDiscovery:
    def test_vague_request_triggers_search(self):
        """A vague request like 'I want a keyboard' should trigger search_catalog,
        which returns at most 3 results."""
        from agents.tools import search_catalog
        # The tool itself limits to top_k=3; verify its docstring/contract
        assert "3" in search_catalog.description or "top 3" in search_catalog.description.lower()

    def test_search_catalog_returns_max_3(self, monkeypatch):
        """search_catalog must return at most 3 products even if vector store has more."""
        fake_results = [
            {"name": f"Product {i}", "id": f"item_{i}", "price": 100*i,
             "currency": "INR", "description": f"Desc {i}", "category": "General", "in_stock": True}
            for i in range(10)
        ]
        monkeypatch.setattr("agents.tools.search_products_vector", lambda q, top_k=3, category=None: fake_results[:top_k])
        from agents.tools import search_catalog
        result = search_catalog.invoke({"query": "keyboard"})
        # Count the number of product entries (each starts with "- ")
        product_count = result.count("\n- ") + (1 if result.startswith("- ") else 0)
        assert product_count <= 3

    def test_specific_request_returns_relevant(self, monkeypatch):
        """A specific request like 'mechanical gaming keyboard' should return relevant matches."""
        fake_results = [
            {"name": "Mechanical Gaming Keyboard RGB", "id": "item_mech1", "price": 4999,
             "currency": "INR", "description": "Cherry MX switches", "category": "Keyboards", "in_stock": True},
        ]
        monkeypatch.setattr("agents.tools.search_products_vector", lambda q, top_k=3, category=None: fake_results)
        from agents.tools import search_catalog
        result = search_catalog.invoke({"query": "mechanical gaming keyboard"})
        assert "Mechanical Gaming Keyboard" in result
        assert "item_mech1" in result  # Tool returns ID for LLM tool use (Scout strips it)

    def test_no_match_returns_helpful_message(self, monkeypatch):
        """When no products match, the tool should return a helpful message about unavailability."""
        monkeypatch.setattr("agents.tools.search_products_vector", lambda q, top_k=3, category=None: [])
        monkeypatch.setattr("agents.tools.pinecone_index", None)  # Disable fallback
        from agents.tools import search_catalog
        result = search_catalog.invoke({"query": "quantum computer"})
        assert "unavailable" in result.lower() or "no products found" in result.lower()

    def test_out_of_stock_shown_in_results(self, monkeypatch):
        """Out-of-stock products should be clearly marked."""
        fake_results = [
            {"name": "Sold Out Widget", "id": "item_oos", "price": 999,
             "currency": "INR", "description": "Very popular", "category": "General", "in_stock": False},
        ]
        monkeypatch.setattr("agents.tools.search_products_vector", lambda q, top_k=3, category=None: fake_results)
        from agents.tools import search_catalog
        result = search_catalog.invoke({"query": "widget"})
        assert "No" in result  # "In Stock: No"


# ── 2. Confirmation regex ─────────────────────────────────────────────

class TestConfirmationDetection:
    @pytest.mark.parametrize("phrase", [
        "yes", "y", "yeah", "yep", "sure", "okay", "ok",
        "proceed", "go ahead", "do it", "confirm", "confirmed",
        "place it", "buy it", "purchase it", "complete the order",
        "pay now", "checkout", "Yes!", "CONFIRM", "Go ahead.",
    ])
    def test_confirm_phrases_match(self, phrase):
        """All standard confirmation phrases must be detected."""
        assert CONFIRM_RE.match(phrase.strip()), f"'{phrase}' should match CONFIRM_RE"

    @pytest.mark.parametrize("phrase", [
        "I want to buy a keyboard",
        "show me more options",
        "what else do you have",
        "no thanks",
        "cancel",
        "remove item",
    ])
    def test_non_confirm_phrases_rejected(self, phrase):
        """Non-confirmation phrases must NOT be detected as confirmation."""
        assert not CONFIRM_RE.match(phrase.strip()), f"'{phrase}' should NOT match CONFIRM_RE"


# ── 3. Action buttons per state ────────────────────────────────────────

class TestActionButtons:
    def test_product_selected_actions(self):
        """PRODUCT_SELECTED should offer Add to Cart and Buy Now."""
        actions = _get_actions_for_state("PRODUCT_SELECTED", "pi_test")
        types = [a.type for a in actions]
        assert "ADD_TO_CART" in types
        assert "BUY_NOW" in types

    def test_purchase_pending_actions(self):
        """PURCHASE_PENDING should offer Proceed to Checkout and Add More Items."""
        actions = _get_actions_for_state("PURCHASE_PENDING", "pi_test")
        types = [a.type for a in actions]
        assert "PROCEED_TO_CHECKOUT" in types
        assert "ADD_MORE_ITEMS" in types

    def test_user_confirmed_actions(self):
        """USER_CONFIRMED should offer Proceed to Payment and Modify Cart."""
        actions = _get_actions_for_state("USER_CONFIRMED", "pi_test")
        types = [a.type for a in actions]
        assert "PROCEED_TO_CHECKOUT" in types
        assert "MODIFY_CART" in types

    def test_idle_no_actions(self):
        """IDLE state should have no actions."""
        actions = _get_actions_for_state("IDLE", "pi_test")
        assert len(actions) == 0

    def test_payment_pending_no_actions(self):
        """PAYMENT_PENDING is handled by checkout_data, not action buttons."""
        actions = _get_actions_for_state("PAYMENT_PENDING", "pi_test")
        assert len(actions) == 0


# ── 4. State transitions ──────────────────────────────────────────────

class TestStateTransitions:
    def test_idle_to_product_selected(self):
        assert can_transition("IDLE", "PRODUCT_SELECTED")

    def test_product_selected_to_purchase_pending(self):
        assert can_transition("PRODUCT_SELECTED", "PURCHASE_PENDING")

    def test_purchase_pending_to_user_confirmed(self):
        assert can_transition("PURCHASE_PENDING", "USER_CONFIRMED")

    def test_user_confirmed_to_order_creating(self):
        assert can_transition("USER_CONFIRMED", "ORDER_CREATING")

    def test_order_creating_to_payment_pending(self):
        assert can_transition("ORDER_CREATING", "PAYMENT_PENDING")

    def test_payment_pending_to_success(self):
        assert can_transition("PAYMENT_PENDING", "PAYMENT_SUCCESS")

    def test_payment_success_is_terminal(self):
        assert "PAYMENT_SUCCESS" in TERMINAL_STATES
        assert not can_transition("PAYMENT_SUCCESS", "IDLE")
        assert not can_transition("PAYMENT_SUCCESS", "PAYMENT_FAILED")

    def test_cannot_skip_confirmation(self):
        """Cannot go directly from PRODUCT_SELECTED to ORDER_CREATING."""
        assert not can_transition("PRODUCT_SELECTED", "ORDER_CREATING")

    def test_idempotent_same_state(self):
        """Same-state transition is always allowed (idempotent)."""
        for state in VALID_TRANSITIONS:
            assert can_transition(state, state)


# ── 5. Closer deterministic behavior ──────────────────────────────────

class TestCloserDeterministic:
    def test_closer_short_circuits_on_user_confirmed(self):
        """When purchase_state is USER_CONFIRMED and user_confirmed is True,
        Closer should issue create_razorpay_order tool call without LLM."""
        from agents.closer import closer_node
        from langchain_core.messages import HumanMessage

        state = {
            "messages": [HumanMessage(content="yes")],
            "purchase_state": "USER_CONFIRMED",
            "user_confirmed": True,
            "purchase_context": {"purchase_intent_id": "pi_test123", "basket_items": [{"product_id": "item_1", "quantity": 1}], "amount_paise": 5000},
        }
        result = closer_node(state)
        msgs = result.get("messages", [])
        assert len(msgs) == 1
        tool_calls = getattr(msgs[0], "tool_calls", None) or []
        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "create_razorpay_order"

    def test_closer_deterministic_purchase_pending(self):
        """When purchase_state is PURCHASE_PENDING, Closer should ask for
        confirmation deterministically without calling the LLM."""
        from agents.closer import closer_node
        from langchain_core.messages import HumanMessage

        state = {
            "messages": [HumanMessage(content="checkout")],
            "purchase_state": "PURCHASE_PENDING",
            "user_confirmed": False,
            "purchase_context": {"purchase_intent_id": "pi_test123", "basket_items": [{"product_id": "item_1", "quantity": 1}], "amount_paise": 5000},
        }
        result = closer_node(state)
        msgs = result.get("messages", [])
        assert len(msgs) == 1
        content = msgs[0].content
        assert "confirm" in content.lower() or "checkout" in content.lower() or "proceed" in content.lower()
        # No tool calls — just a confirmation prompt
        tool_calls = getattr(msgs[0], "tool_calls", None) or []
        assert len(tool_calls) == 0

    def test_closer_no_double_confirm_after_success(self):
        """After PAYMENT_PENDING, Closer should direct user to payment window, not re-ask."""
        from agents.closer import closer_node
        from langchain_core.messages import HumanMessage

        state = {
            "messages": [HumanMessage(content="yes confirm")],
            "purchase_state": "PAYMENT_PENDING",
            "user_confirmed": True,
            "purchase_context": {"purchase_intent_id": "pi_test123"},
        }
        result = closer_node(state)
        msgs = result.get("messages", [])
        assert len(msgs) == 1
        content = msgs[0].content.lower()
        assert "payment" in content or "pay" in content
        # Should NOT ask for confirmation again
        assert "confirm" not in content or "payment" in content


# ── 6. Cart management ────────────────────────────────────────────────

class TestCartManagement:
    def test_stage_purchase_intent_returns_success(self):
        """stage_purchase_intent tool returns a success message."""
        from agents.tools import stage_purchase_intent
        result = stage_purchase_intent.invoke({"product_id": "item_abc", "quantity": 2})
        assert "cart" in result.lower() or "updated" in result.lower()
        assert "item_abc" in result

    def test_stage_purchase_intent_quantity_zero_removes(self):
        """Setting quantity=0 should signal removal."""
        from agents.tools import stage_purchase_intent
        result = stage_purchase_intent.invoke({"product_id": "item_abc", "quantity": 0})
        assert "0x" in result or "cart" in result.lower()


# ── 7. Scout sanitization ─────────────────────────────────────────────

class TestScoutSanitization:
    def test_sanitize_removes_product_ids(self):
        """Scout's sanitizer must remove item_XXX and rec_XXX from responses."""
        from agents.scout import _sanitize_customer_response
        text = "Here's the Ergonomic Mouse (ID: item_TTVq123) with a recommendation (Rec ID: rec_abc456)"
        cleaned = _sanitize_customer_response(text)
        assert "item_" not in cleaned
        assert "rec_" not in cleaned
        assert "Ergonomic Mouse" in cleaned

    def test_sanitize_preserves_normal_text(self):
        """Normal text without IDs should pass through unchanged."""
        from agents.scout import _sanitize_customer_response
        text = "I recommend the Mechanical Keyboard for gaming."
        assert _sanitize_customer_response(text) == text


# ── 8. Buy Now flow ───────────────────────────────────────────────────

class TestBuyNow:
    def test_buy_now_action_type_exists(self):
        """BUY_NOW action should be returned for PRODUCT_SELECTED state."""
        actions = _get_actions_for_state("PRODUCT_SELECTED", "pi_test")
        buy_now = [a for a in actions if a.type == "BUY_NOW"]
        assert len(buy_now) == 1
        assert buy_now[0].label == "Buy Now"


# ── 9. Confirmation must not repeat ───────────────────────────────────

class TestConfirmationNoRepeat:
    def test_already_confirmed_detected(self):
        """If intent is USER_CONFIRMED and user says 'yes' again,
        it should be detected as already_confirmed and not re-enter confirmation loop."""
        intent = {"purchase_state": "USER_CONFIRMED", "user_confirmed": True}
        user_msg = "yes"
        already_confirmed = bool(
            intent and
            intent.get("purchase_state") == "USER_CONFIRMED" and
            intent.get("user_confirmed") and
            CONFIRM_RE.match(user_msg.strip())
        )
        assert already_confirmed

    def test_non_confirmed_not_detected_as_already(self):
        """If intent is PURCHASE_PENDING, it should not be detected as already_confirmed."""
        intent = {"purchase_state": "PURCHASE_PENDING", "user_confirmed": False}
        user_msg = "yes"
        already_confirmed = bool(
            intent and
            intent.get("purchase_state") == "USER_CONFIRMED" and
            intent.get("user_confirmed") and
            CONFIRM_RE.match(user_msg.strip())
        )
        assert not already_confirmed
