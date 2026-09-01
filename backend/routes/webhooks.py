from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Request, HTTPException
from utils.supabase_client import supabase
from razorpay_service.client import rzp
from razorpay.errors import SignatureVerificationError
from config import settings
from agents.ledger import log_agent_action
from agents.payment_state import can_transition, is_terminal

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def _local_order(rzp_order_id: str):
    mapping = (supabase.table("entity_mapping").select("synthetic_id")
               .eq("entity_type", "order").eq("razorpay_id", rzp_order_id).limit(1).execute())
    if not mapping.data:
        return None
    result = supabase.table("orders").select("*").eq("order_id", mapping.data[0]["synthetic_id"]).maybe_single().execute()
    return result.data if result.data else None


@router.post("/razorpay/webhook")
async def handle_razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # ── MANDATORY signature verification ──────────────────────────────
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured — rejecting webhook")
        raise HTTPException(status_code=500, detail="Webhook processing unavailable")

    try:
        rzp.utility.verify_webhook_signature(body.decode(), signature, secret)
    except SignatureVerificationError:
        logger.warning("Invalid Razorpay webhook signature from %s", request.client.host)
        raise HTTPException(status_code=400, detail="Invalid signature")

    # ── Parse only after verification ─────────────────────────────────
    payload = await request.json()
    event = payload.get("event", "")
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    rzp_order_id = payment.get("order_id")
    rzp_payment_id = payment.get("id")

    if not rzp_order_id or not rzp_payment_id:
        return {"status": "ignored", "reason": "missing identifiers"}

    # ── Webhook idempotency ───────────────────────────────────────────
    event_id = str(payload.get("id") or f"{event}:{rzp_payment_id}")
    received_at = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("webhook_events").insert({
            "event_id": event_id,
            "event_type": event,
            "razorpay_entity_id": rzp_payment_id,
            "received_at": received_at,
            "status": "RECEIVED"
        }).execute()
    except Exception:
        existing = supabase.table("webhook_events").select("event_id").eq("event_id", event_id).maybe_single().execute()
        if existing and existing.data:
            logger.info("Duplicate webhook event %s — ignoring", event_id)
            return {"status": "duplicate"}
        raise

    # ── Route by event type ───────────────────────────────────────────
    if event == "payment.authorized":
        # Payment authorized but not yet captured — keep as PAYMENT_PENDING
        supabase.table("webhook_events").update({
            "status": "PROCESSED", "processed_at": received_at
        }).eq("event_id", event_id).execute()
        log_agent_action(agent_name="Webhook", action_type=event,
                         status="SUCCESS", input_summary=f"Razorpay order {rzp_order_id}",
                         output_summary="Payment authorized, awaiting capture",
                         razorpay_entity_id=rzp_payment_id)
        return {"status": "ok"}

    if event not in {"payment.captured", "payment.failed", "order.paid"}:
        supabase.table("webhook_events").update({
            "status": "IGNORED", "processed_at": received_at
        }).eq("event_id", event_id).execute()
        return {"status": "ignored"}

    # ── Determine target state ────────────────────────────────────────
    if event in {"payment.captured", "order.paid"}:
        target_status = "CAPTURED"
    else:
        target_status = "FAILED"

    # ── Authoritative Payment Resolution ──────────────────────────────
    from services.payment_resolution import resolve_payment_status
    amount = int(payment.get("amount") or 0)
    res = resolve_payment_status(rzp_order_id, rzp_payment_id, amount, target_status, source="webhook")

    if res.get("status") == "error":
        supabase.table("webhook_events").update({
            "status": "ERROR", "error": res.get("reason"), "processed_at": received_at
        }).eq("event_id", event_id).execute()
        raise HTTPException(status_code=400, detail="Validation failed")
        
    if res.get("status") == "ignored":
        supabase.table("webhook_events").update({
            "status": "IGNORED", "processed_at": received_at
        }).eq("event_id", event_id).execute()
        return {"status": "ignored", "reason": res.get("reason")}

    # Update recommendations if converted
    if target_status == "CAPTURED" and res.get("state") == "PAYMENT_SUCCESS":
        try:
            # We need intent_id and order_id to update recommendations
            mapping = (supabase.table("entity_mapping").select("synthetic_id")
                       .eq("entity_type", "order").eq("razorpay_id", rzp_order_id).limit(1).execute())
            if mapping.data:
                order_id = mapping.data[0]["synthetic_id"]
                order_data = (lambda r: getattr(r, "data", None))(supabase.table("orders").select("purchase_intent_id").eq("order_id", order_id).maybe_single().execute())
                if order_data:
                    intent_id = order_data["purchase_intent_id"]
                    intent = supabase.table("purchase_intents").select("recommendation_id").eq("purchase_intent_id", intent_id).maybe_single().execute()
                    rec_id = (intent.data or {}).get("recommendation_id")
                    if rec_id:
                        supabase.table("recommendation_events").update({
                            "status": "CONVERTED",
                            "resulting_order_id": order_id,
                            "revenue_paise": amount
                        }).eq("recommendation_id", rec_id).eq("status", "ACCEPTED").execute()
        except Exception as e:
            logger.error("Failed to update recommendation status: %s", e)

    log_agent_action(
        agent_name="Webhook", action_type=event,
        status="SUCCESS" if target_status == "CAPTURED" else "REJECTED",
        input_summary=f"Razorpay order {rzp_order_id}",
        output_summary=f"Payment {target_status}",
        razorpay_entity_id=rzp_payment_id
    )
    supabase.table("webhook_events").update({
        "status": "PROCESSED", "processed_at": received_at
    }).eq("event_id", event_id).execute()
    return {"status": "ok"}
