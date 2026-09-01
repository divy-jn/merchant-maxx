import logging
from config import settings
from utils.supabase_client import supabase
import json

logger = logging.getLogger(__name__)


def log_agent_action(
    agent_name: str, 
    action_type: str, 
    status: str, 
    input_summary: str = "",
    output_summary: str = "",
    reasoning: str = "",
    risk_score: float = 0.0,
    constitutional_check: dict = None,
    razorpay_entity_id: str = None,
    session_id: str = None,
    customer_id: str = None,
    entity_type: str = None,
    entity_id: str = None,
    purchase_state: str = None
):
    """Logs agent decisions to the Supabase audit trail for explainability"""
    
    log_entry = {
        "agent_name": agent_name,
        "action_type": action_type,
        "status": status,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "reasoning": reasoning,
        "risk_score": risk_score,
        "constitutional_check": constitutional_check or {},
        "razorpay_entity_id": razorpay_entity_id,
        "session_id": session_id,
        "customer_id": customer_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "purchase_state": purchase_state
    }
    
    logger.info(f"[LEDGER] {agent_name} | {action_type} | {status} | Risk: {risk_score}")
    
    if supabase:
        try:
            # For backward compatibility, still write to audit_log
            supabase.table("audit_log").insert({
                "agent_name": agent_name,
                "action_type": action_type,
                "status": status,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "reasoning": reasoning,
                "risk_score": risk_score,
                "constitutional_check": constitutional_check or {},
                "razorpay_entity_id": razorpay_entity_id
            }).execute()
            
            # Write to the new comprehensive agent_audit table
            import uuid
            supabase.table("agent_audit").insert({
                "audit_id": f"aud_{uuid.uuid4().hex[:12]}",
                "session_id": session_id,
                "customer_id": customer_id,
                "agent_name": agent_name,
                "action_type": action_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "status": status,
                "risk_score": risk_score,
                "reasoning": reasoning,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "razorpay_entity_id": razorpay_entity_id,
                "purchase_state": purchase_state
            }).execute()
        except Exception as e:
            logger.error(f"Failed to write to Supabase audit log: {e}")
    else:
        logger.warning("[LEDGER] Supabase not connected. Log only available in console.")
