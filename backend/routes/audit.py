from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from agents.ledger import supabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/")
def get_audit_logs(limit: int = 50):
    """Fetches recent audit logs from Supabase"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured or connected.")
        
    try:
        response = supabase.table("audit_log").select("*").order("timestamp", desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        if 'PGRST205' in str(e):
            logger.warning("Audit table not found, returning empty logs.")
            return []
        logger.error(f"Error fetching audit logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{log_id}")
def get_audit_log(log_id: str):
    """Fetches a specific audit log by ID"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured.")
        
    try:
        response = supabase.table("audit_log").select("*").eq("id", log_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Log not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
