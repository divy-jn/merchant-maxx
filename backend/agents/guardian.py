from audit.constitutional import evaluate_safety
from agents.ledger import log_agent_action
import logging

logger = logging.getLogger(__name__)

class GuardianException(Exception):
    pass

def validate_action(agent_name: str, action_type: str, action_intent: dict, amount_paise: int = 0) -> bool:
    """
    The Safety Gate for all money actions.
    Must be called BEFORE any Razorpay API interaction.
    """
    logger.info(f"[GUARDIAN] Validating {action_type} from {agent_name} for amount {amount_paise}")
    
    # 1. Run constitutional checks
    eval_result = evaluate_safety(action_intent, amount_paise)
    
    # 2. Log decision to Ledger
    status = "APPROVED" if eval_result.passed else "REJECTED"
    log_agent_action(
        agent_name=agent_name,
        action_type=action_type,
        status=status,
        input_summary=f"Intent: {action_intent.get('description', 'Unknown')}",
        output_summary=f"Guardian decision: {status}",
        reasoning=eval_result.reasoning,
        risk_score=eval_result.risk_score,
        constitutional_check={
            "violations": eval_result.violations,
            "passed": eval_result.passed
        }
    )
    
    # 3. Block or Allow
    if not eval_result.passed:
        violations_str = ", ".join(eval_result.violations)
        raise GuardianException(f"Guardian blocked action due to safety violations: {violations_str}")
        
    return True
