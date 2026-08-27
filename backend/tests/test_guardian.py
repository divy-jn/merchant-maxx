import pytest
from audit.constitutional import evaluate_safety
from config import settings


def base(**overrides):
    data = {
        "action_type": "create_razorpay_order",
        "purchase_state": "USER_CONFIRMED",
        "user_confirmed": True,
        "entity_valid": True,
        "is_duplicate": False,
    }
    data.update(overrides)
    return data


def test_valid_order_is_allowed():
    result = evaluate_safety(base(), 10000)
    assert result.passed


def test_confirmation_is_required():
    result = evaluate_safety(base(user_confirmed=False), 10000)
    assert not result.passed
    assert any("RULE_02" in v for v in result.violations)


def test_duplicate_is_blocked():
    result = evaluate_safety(base(is_duplicate=True), 10000)
    assert not result.passed
    assert any("RULE_05" in v for v in result.violations)


def test_invalid_state_is_blocked():
    result = evaluate_safety(base(purchase_state="PURCHASE_PENDING"), 10000)
    assert not result.passed
    assert any("RULE_06" in v for v in result.violations)


def test_invalid_entity_is_blocked():
    result = evaluate_safety(base(entity_valid=False), 10000)
    assert not result.passed
    assert any("RULE_07" in v for v in result.violations)


def test_failed_payment_retry_is_blocked():
    result = evaluate_safety(base(purchase_state="PAYMENT_FAILED"), 10000)
    assert not result.passed
    assert any("RULE_08" in v for v in result.violations)


def test_over_limit_is_blocked():
    result = evaluate_safety(base(), settings.GUARDIAN_MAX_TRANSACTION_PAISE + 1)
    assert not result.passed
    assert any("RULE_01" in v for v in result.violations)
