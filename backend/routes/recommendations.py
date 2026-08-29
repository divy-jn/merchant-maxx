from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

@router.post("/{rec_id}/shown")
def mark_shown(rec_id: str):
    if not supabase:
        return {"status": "skipped", "reason": "No DB"}
    try:
        supabase.table("recommendation_events").update({"status": "SHOWN"}).eq("recommendation_id", rec_id).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error marking shown: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{rec_id}/clicked")
def mark_clicked(rec_id: str):
    if not supabase:
        return {"status": "skipped"}
    try:
        supabase.table("recommendation_events").update({"status": "CLICKED"}).eq("recommendation_id", rec_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{rec_id}/accepted")
def mark_accepted(rec_id: str):
    if not supabase:
        return {"status": "skipped"}
    try:
        supabase.table("recommendation_events").update({"status": "ACCEPTED"}).eq("recommendation_id", rec_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{rec_id}/dismissed")
def mark_dismissed(rec_id: str):
    if not supabase:
        return {"status": "skipped"}
    try:
        supabase.table("recommendation_events").update({"status": "DISMISSED"}).eq("recommendation_id", rec_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
