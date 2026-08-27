from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from config import settings
import logging

logger = logging.getLogger(__name__)

class SafetyRule(BaseModel):
    id: str
    description: str
    severity: str # 'BLOCK' or 'WARN'

class ConstitutionalCheckResult(BaseModel):
    passed: bool
    violations: List[str] = []
    risk_score: float = 0.0 # 0.0 (safe) to 1.0 (unsafe)
    reasoning: str = ""

CONSTITUTIONAL_RULES = [
    SafetyRule(
        id="RULE_01_MAX_TX_LIMIT",
        description=f"Transaction amount must not exceed {settings.GUARDIAN_MAX_TRANSACTION_PAISE / 100} INR.",
        severity="BLOCK"
    ),
    SafetyRule(
        id="RULE_02_USER_CONFIRMATION",
        description="Agent must have explicit user confirmation before initiating payment.",
        severity="BLOCK"
    ),
    SafetyRule(
        id="RULE_03_PII_PROTECTION",
        description="Agent must not expose full credit card numbers or passwords.",
        severity="BLOCK"
    ),
    SafetyRule(
        id="RULE_04_NO_SELF_DEALING",
        description="Agent cannot purchase items for itself or transfer funds to unrecognized accounts.",
        severity="BLOCK"
    ),
    SafetyRule(
        id="RULE_05_IDEMPOTENCY",
        description="Duplicate action detection. Exact same action cannot be re-executed.",
        severity="BLOCK"
    ),
    SafetyRule(
        id="RULE_06_VALID_STATE",
        description="Action must align with the current purchase state.",
        severity="BLOCK"
    ),
    SafetyRule(
        id="RULE_07_VALID_ENTITY",
        description="Action must reference valid entities.",
        severity="BLOCK"
    ),
    SafetyRule(
        id="RULE_08_NO_BLIND_RETRY",
        description="Do not blindly retry after FAILED/UNKNOWN payment. Must inspect state first.",
        severity="BLOCK"
    )
]

def evaluate_safety(action_intent: dict, amount_paise: int = 0) -> ConstitutionalCheckResult:
    """Evaluates an action against the constitutional rules (simulated deterministic checks + LLM logic)"""
    violations = []
    risk = 0.0
    
    # Deterministic checks
    if amount_paise > settings.GUARDIAN_MAX_TRANSACTION_PAISE:
        violations.append("RULE_01_MAX_TX_LIMIT: Amount exceeds maximum allowed transaction limit.")
        risk += 0.8
        
    if settings.GUARDIAN_REQUIRE_CONFIRMATION and not action_intent.get("user_confirmed", False):
        violations.append("RULE_02_USER_CONFIRMATION: Missing explicit user confirmation.")
        risk += 0.6
        
    # NEW RULE IMPLEMENTATIONS
    state = action_intent.get("purchase_state", "")
    
    if action_intent.get("is_duplicate", False):
        violations.append("RULE_05_IDEMPOTENCY: Duplicate action detected based on intent identifier.")
        risk += 0.9
        
    if state == "PAYMENT_FAILED" and action_intent.get("action_type") == "retry_payment" and not action_intent.get("state_inspected", False):
        violations.append("RULE_08_NO_BLIND_RETRY: Must inspect actual payment state before retrying after failure.")
        risk += 1.0
        
    # In a full implementation, we would use an LLM here to evaluate RULE_03 and RULE_04
    # against the conversational context.
    
    passed = len(violations) == 0
    reasoning = "All safety checks passed." if passed else "Safety violations detected. Blocking action."
    
    return ConstitutionalCheckResult(
        passed=passed,
        violations=violations,
        risk_score=min(risk, 1.0),
        reasoning=reasoning
    )
