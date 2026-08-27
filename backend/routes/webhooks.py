from fastapi import APIRouter, Request, HTTPException
from utils.supabase_client import supabase
from razorpay_service.client import rzp
from razorpay.errors import SignatureVerificationError
from config import settings
from agents.ledger import log_agent_action
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def _local_order(rzp_order_id: str):
    mapping = (supabase.table("entity_mapping").select("synthetic_id")
               .eq("entity_type", "order").eq("razorpay_id", rzp_order_id).limit(1).execute())
    if not mapping.data:
        return None
    order = supabase.table("orders").select("*").eq("order_id", mapping.data[0]["synthetic_id"]).maybe_single().execute()
    return order.data if order.data else None

@router.post("/razorpay/webhook")
async def handle_razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
    if secret:
        try:
            rzp.utility.verify_webhook_signature(body.decode(), signature, secret)
        except SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
    payload = await request.json()
    event = payload.get("event", "")
    event_id = payload.get("account_id", "") + ":" + str(payload.get("created_at", "")) + ":" + event + ":" + str(payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id", ""))
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    rzp_order_id, rzp_payment_id = payment.get("order_id"), payment.get("id")
    if not rzp_order_id or not rzp_payment_id:
        return {"status": "ignored", "reason": "missing payment identifiers"}

    # Persist webhook idempotency before side effects.
    try:
        inserted = supabase.table("webhook_events").insert({"event_id": event_id, "event_type": event, "razorpay_entity_id": rzp_payment_id, "status": "RECEIVED"}).execute()
        if not inserted.data:
            return {"status": "duplicate"}
    except Exception:
        existing = supabase.table("webhook_events").select("event_id").eq("event_id", event_id).maybe_single().execute()
        if existing.data:
            return {"status": "duplicate"}
        raise

    order = _local_order(rzp_order_id)
    if not order:
        supabase.table("webhook_events").update({"status": "IGNORED", "processed_at": "now()"}).eq("event_id", event_id).execute()
        return {"status": "ignored", "reason": "unmapped Razorpay order"}

    amount = int(payment.get("amount") or 0)
    if amount != int(order.get("total_paise") or 0):
        supabase.table("webhook_events").update({"status": "ERROR", "error": "amount mismatch"}).eq("event_id", event_id).execute()
        raise HTTPException(status_code=400, detail="Payment amount does not match local order")

    status = "CAPTURED" if event == "payment.captured" else "FAILED" if event == "payment.failed" else None
    if not status:
        supabase.table("webhook_events").update({"status": "IGNORED", "processed_at": "now()"}).eq("event_id", event_id).execute()
        return {"status": "ignored"}

    supabase.table("payments").upsert({
        "payment_id": f"pay_{rzp_payment_id}", "order_id": order["order_id"], "customer_id": order.get("customer_id"),
        "amount_paise": amount, "currency": payment.get("currency", "INR"), "status": status,
        "method": payment.get("method"), "failure_code": payment.get("error_code"),
        "failure_reason": payment.get("error_description"), "razorpay_payment_id": rzp_payment_id
    }, on_conflict="payment_id").execute()
    supabase.table("entity_mapping").upsert({"synthetic_id": f"pay_{rzp_payment_id}", "entity_type": "payment", "razorpay_id": rzp_payment_id}, on_conflict="merchant_id,entity_type,synthetic_id").execute()

    intent_id = None
    intent_q = supabase.table("orders").select("purchase_intent_id").eq("order_id", order["order_id"]).maybe_single().execute()
    if intent_q.data:
        intent_id = intent_q.data.get("purchase_intent_id")
    if intent_id:
        new_state = "PAYMENT_SUCCESS" if status == "CAPTURED" else "PAYMENT_FAILED"
        supabase.table("purchase_intents").update({"purchase_state": new_state, "razorpay_payment_id": rzp_payment_id}).eq("purchase_intent_id", intent_id).execute()

        if status == "CAPTURED":
            intent = supabase.table("purchase_intents").select("recommendation_id").eq("purchase_intent_id", intent_id).maybe_single().execute()
            rec_id = (intent.data or {}).get("recommendation_id")
            if rec_id:
                supabase.table("recommendation_events").update({"status": "CONVERTED", "resulting_order_id": order["order_id"], "revenue_paise": amount}).eq("recommendation_id", rec_id).eq("status", "ACCEPTED").execute()

    log_agent_action(agent_name="Webhook", action_type=event, status="SUCCESS" if status == "CAPTURED" else "REJECTED",
                     input_summary=f"Razorpay order {rzp_order_id}", output_summary=f"Payment {status}", razorpay_entity_id=rzp_payment_id)
    supabase.table("webhook_events").update({"status": "PROCESSED", "processed_at": "now()"}).eq("event_id", event_id).execute()
    return {"status": "ok"}
