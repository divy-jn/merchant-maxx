from pydantic import BaseModel
from typing import List
from config import settings

class SafetyRule(BaseModel):
    id: str
    description: str
    severity: str

class ConstitutionalCheckResult(BaseModel):
    passed: bool
    violations: List[str] = []
    risk_score: float = 0.0
    reasoning: str = ""

CONSTITUTIONAL_RULES = [
    SafetyRule(id="RULE_01_MAX_TX_LIMIT", description=f"Transaction amount must not exceed {settings.GUARDIAN_MAX_TRANSACTION_PAISE / 100} INR.", severity="BLOCK"),
    SafetyRule(id="RULE_02_USER_CONFIRMATION", description="Explicit user confirmation is required.", severity="BLOCK"),
    SafetyRule(id="RULE_03_PII_PROTECTION", description="Do not expose sensitive credentials or payment data.", severity="BLOCK"),
    SafetyRule(id="RULE_04_NO_SELF_DEALING", description="No self-directed or unrecognized money movement.", severity="BLOCK"),
    SafetyRule(id="RULE_05_IDEMPOTENCY", description="A purchase intent can create at most one order.", severity="BLOCK"),
    SafetyRule(id="RULE_06_VALID_STATE", description="Money actions must align with the purchase state machine.", severity="BLOCK"),
    SafetyRule(id="RULE_07_VALID_ENTITY", description="Products, merchant, basket and amount must be server-validated.", severity="BLOCK"),
    SafetyRule(id="RULE_08_NO_BLIND_RETRY", description="FAILED/UNKNOWN payments require inspection and a fresh purchase intent.", severity="BLOCK"),
]

def evaluate_safety(action_intent: dict, amount_paise: int = 0) -> ConstitutionalCheckResult:
    violations, risk = [], 0.0
    if amount_paise > settings.GUARDIAN_MAX_TRANSACTION_PAISE:
        violations.append("RULE_01_MAX_TX_LIMIT: Amount exceeds the maximum transaction limit."); risk += 0.8
    if settings.GUARDIAN_REQUIRE_CONFIRMATION and not action_intent.get("user_confirmed", False):
        violations.append("RULE_02_USER_CONFIRMATION: Missing explicit user confirmation."); risk += 0.6
    action_type = action_intent.get("action_type")
    state = action_intent.get("purchase_state", "IDLE")
    if action_intent.get("pii_violation", False):
        violations.append("RULE_03_PII_PROTECTION: Sensitive data handling violation."); risk += 0.9
    if action_intent.get("self_dealing", False):
        violations.append("RULE_04_NO_SELF_DEALING: Unrecognized/self-directed money action."); risk += 0.9
    if action_intent.get("is_duplicate", False):
        violations.append("RULE_05_IDEMPOTENCY: Purchase intent has already produced an order."); risk += 0.9
    if action_type == "create_razorpay_order" and state != "USER_CONFIRMED":
        violations.append(f"RULE_06_VALID_STATE: Cannot create an order in state {state}; expected USER_CONFIRMED."); risk += 0.7
    if action_type == "create_razorpay_order" and not action_intent.get("entity_valid", True):
        violations.append("RULE_07_VALID_ENTITY: Basket, product, merchant or amount validation failed."); risk += 0.9
    if action_type == "create_razorpay_order" and state in {"PAYMENT_FAILED", "PAYMENT_UNKNOWN"}:
        violations.append("RULE_08_NO_BLIND_RETRY: Inspect payment state and create a fresh intent before retrying."); risk += 1.0
    passed = not violations
    return ConstitutionalCheckResult(passed=passed, violations=violations, risk_score=min(risk, 1.0), reasoning="All safety checks passed." if passed else "Safety violations detected. Action blocked.")
