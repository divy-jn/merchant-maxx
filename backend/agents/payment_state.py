"""
Payment state machine — authoritative transition rules.

Every state change to purchase_intents.purchase_state MUST go through
can_transition() or assert_transition().  Terminal states are immutable
unless an explicit reconciliation path is added here.
"""

import logging

logger = logging.getLogger(__name__)

# ── Valid transitions ────────────────────────────────────────────────
VALID_TRANSITIONS: dict[str, set[str]] = {
    "IDLE":                  {"PRODUCT_SELECTED"},
    "PRODUCT_SELECTED":      {"RECOMMENDATION_SHOWN", "PURCHASE_PENDING"},
    "RECOMMENDATION_SHOWN":  {"PURCHASE_PENDING", "USER_CONFIRMED"},
    "PURCHASE_PENDING":      {"USER_CONFIRMED"},
    "USER_CONFIRMED":        {"ORDER_CREATING"},
    "ORDER_CREATING":        {"PAYMENT_PENDING", "USER_CONFIRMED", "PAYMENT_FAILED"},
    "PAYMENT_PENDING":       {"PAYMENT_SUCCESS", "PAYMENT_FAILED"},
    "PAYMENT_FAILED":        {"RECOVERY_PENDING"},
    "RECOVERY_PENDING":      {"PURCHASE_PENDING"},
    # PAYMENT_SUCCESS is terminal — no outgoing transitions allowed
}

TERMINAL_STATES = frozenset({"PAYMENT_SUCCESS"})


def can_transition(from_state: str, to_state: str) -> bool:
    """Return True if the transition is permitted."""
    if from_state == to_state:
        return True  # idempotent no-op
    if from_state in TERMINAL_STATES:
        return False
    return to_state in VALID_TRANSITIONS.get(from_state, set())


def assert_transition(from_state: str, to_state: str) -> None:
    """Raise ValueError if the transition is illegal."""
    if not can_transition(from_state, to_state):
        raise ValueError(
            f"Illegal payment state transition: {from_state} → {to_state}"
        )


def is_terminal(state: str) -> bool:
    """Return True if state is terminal (no further transitions allowed)."""
    return state in TERMINAL_STATES
