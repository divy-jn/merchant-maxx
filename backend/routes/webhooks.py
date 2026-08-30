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

    # ── Map to local order ────────────────────────────────────────────
    order = _local_order(rzp_order_id)
    intent_id = None
    if not order:
        # Fallback to direct purchase_intent mapping
        intent_res = supabase.table("purchase_intents").select("purchase_intent_id").eq("razorpay_order_id", rzp_order_id).maybe_single().execute()
        if intent_res and intent_res.data:
            intent_id = intent_res.data["purchase_intent_id"]
            logger.warning("Local order missing for %s, falling back to intent %s", rzp_order_id, intent_id)
        else:
            supabase.table("webhook_events").update({
                "status": "IGNORED", "processed_at": received_at
            }).eq("event_id", event_id).execute()
            return {"status": "ignored", "reason": "unmapped order"}
    else:
        intent_id = order.get("purchase_intent_id")

    # ── Amount validation ─────────────────────────────────────────────
    amount = int(payment.get("amount") or 0)
    if order:
        expected_amount = int(order.get("total_paise") or 0)
        if amount != expected_amount:
            supabase.table("webhook_events").update({
                "status": "ERROR", "error": "amount mismatch", "processed_at": received_at
            }).eq("event_id", event_id).execute()
            logger.error("Webhook amount mismatch: got %d, expected %d for order %s", amount, expected_amount, rzp_order_id)
            raise HTTPException(status_code=400, detail="Validation failed")

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
        target_state = "PAYMENT_SUCCESS"
    else:
        target_status = "FAILED"
        target_state = "PAYMENT_FAILED"

    # ── Persist payment record ────────────────────────────────────────
    if order:
        supabase.table("payments").upsert({
            "payment_id": f"pay_{rzp_payment_id}",
            "order_id": order["order_id"],
            "customer_id": order.get("customer_id"),
            "amount_paise": amount,
            "currency": payment.get("currency", "INR"),
            "status": target_status,
            "method": payment.get("method"),
            "failure_code": payment.get("error_code"),
            "failure_reason": payment.get("error_description"),
            "razorpay_payment_id": rzp_payment_id,
            "initiated_at": received_at,
            "completed_at": received_at if target_status == "CAPTURED" else None
        }, on_conflict="payment_id").execute()

        try:
            supabase.table("entity_mapping").insert({
                "synthetic_id": f"pay_{rzp_payment_id}",
                "entity_type": "payment",
                "razorpay_id": rzp_payment_id
            }).execute()
        except Exception:
            pass  # Already mapped

    # ── State downgrade protection (Atomic DB Update) ─────────────────
    if intent_id:
        current_intent = supabase.table("purchase_intents").select("purchase_state, basket").eq(
            "purchase_intent_id", intent_id).maybe_single().execute()
        current_state = (current_intent.data or {}).get("purchase_state", "PAYMENT_PENDING")
        basket = (current_intent.data or {}).get("basket") or []

        if is_terminal(current_state) and target_state != current_state:
            # PAYMENT_SUCCESS → PAYMENT_FAILED is NEVER allowed
            logger.warning(
                "Blocked state downgrade %s → %s for intent %s",
                current_state, target_state, intent_id
            )
        elif can_transition(current_state, target_state):
            fulfillment_status = "PENDING"
            if target_status == "CAPTURED" and order:
                try:
                    rpc_res = supabase.rpc("atomic_inventory_decrement", {
                        "p_order_id": order["order_id"],
                        "p_intent_id": intent_id,
                        "p_items": basket
                    }).execute()
                    
                    status_flag = (rpc_res.data or {}).get("status")
                    if status_flag == "success":
                        fulfillment_status = "FULFILLED"
                        logger.info("Inventory successfully decremented for order %s", order["order_id"])
                    elif status_flag == "already_processed":
                        fulfillment_status = "FULFILLED"
                        logger.info("Inventory already decremented for order %s", order["order_id"])
                    else:
                        raise Exception(f"Unexpected RPC status: {status_flag}")
                        
                except Exception as e:
                    logger.error("Inventory fulfillment failed for order %s: %s", order["order_id"], str(e))
                    fulfillment_status = "UNFULFILLED"
                    from services.refund_service import initiate_refund
                    initiate_refund(rzp_payment_id, amount, "Inventory unavailable")

            # Enforce atomicity: NEVER overwrite a terminal PAYMENT_SUCCESS with a failure
            # If the row is already in PAYMENT_SUCCESS, a failure update will affect 0 rows.
            update_res = supabase.table("purchase_intents").update({
                "purchase_state": target_state,
                "razorpay_payment_id": rzp_payment_id,
                "fulfillment_status": fulfillment_status,
                "updated_at": received_at
            }).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
            
            if order:
                supabase.table("orders").update({
                    "status": target_status,
                    "fulfillment_status": fulfillment_status,
                    "updated_at": received_at
                }).eq("order_id", order["order_id"]).neq("status", "CAPTURED").execute()
            
            # If the update succeeded and we are transitioning to success
            if update_res.data and target_status == "CAPTURED" and order:
                intent = supabase.table("purchase_intents").select("recommendation_id").eq(
                    "purchase_intent_id", intent_id).maybe_single().execute()
                rec_id = (intent.data or {}).get("recommendation_id")
                if rec_id:
                    supabase.table("recommendation_events").update({
                        "status": "CONVERTED",
                        "resulting_order_id": order["order_id"],
                        "revenue_paise": amount
                    }).eq("recommendation_id", rec_id).eq("status", "ACCEPTED").execute()
            
            # If update affected 0 rows, it means the state was concurrently moved to PAYMENT_SUCCESS
            if not update_res.data and target_state != "PAYMENT_SUCCESS":
                logger.warning("TOCTOU PREVENTED: Concurrent transition already marked %s as PAYMENT_SUCCESS, blocked downgrade to %s", intent_id, target_state)
        else:
            logger.info("No-op transition %s → %s for intent %s",
                        current_state, target_state, intent_id)

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
