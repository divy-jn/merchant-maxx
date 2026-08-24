import logging
from config import settings
from supabase import create_client, Client
import json

logger = logging.getLogger(__name__)

supabase: Client = None
if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    except Exception as e:
        logger.error(f"Failed to init Supabase in Ledger: {e}")

def log_agent_action(
    agent_name: str, 
    action_type: str, 
    status: str, 
    input_summary: str = "",
    output_summary: str = "",
    reasoning: str = "",
    risk_score: float = 0.0,
    constitutional_check: dict = None,
    razorpay_entity_id: str = None
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
        "razorpay_entity_id": razorpay_entity_id
    }
    
    logger.info(f"[LEDGER] {agent_name} | {action_type} | {status} | Risk: {risk_score}")
    
    if supabase:
        try:
            # We wrap this in try-except so a DB error doesn't crash the main flow
            supabase.table("audit_log").insert(log_entry).execute()
        except Exception as e:
            logger.error(f"Failed to write to Supabase audit log: {e}")
    else:
        logger.warning("[LEDGER] Supabase not connected. Log only available in console.")
