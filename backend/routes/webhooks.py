from fastapi import APIRouter, Request, HTTPException
from utils.supabase_client import supabase
from razorpay_service.client import rzp
from razorpay.errors import SignatureVerificationError
from config import settings
from agents.ledger import log_agent_action
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

@router.post("/razorpay/webhook")
async def handle_razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    # Optional: Verify webhook signature if secret is configured
    webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
    if webhook_secret:
        try:
            rzp.utility.verify_webhook_signature(body.decode(), signature, webhook_secret)
        except SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
            
    payload = await request.json()
    event = payload.get("event", "")
    entity = payload.get("payload", {})
    
    if event == "payment.captured":
        payment_entity = entity.get("payment", {}).get("entity", {})
        rzp_order_id = payment_entity.get("order_id")
        rzp_payment_id = payment_entity.get("id")
        
        logger.info(f"Webhook received: Payment captured for order {rzp_order_id}")
        
        if rzp_order_id:
            # We don't have a local order table in this simplified schema, but we log it to audit.
            log_agent_action(
                agent_name="Webhook",
                action_type="payment_captured",
                status="SUCCESS",
                input_summary=f"Razorpay Order: {rzp_order_id}",
                output_summary="Payment captured successfully",
                razorpay_entity_id=rzp_payment_id
            )
            
            # Revenue Attribution: Mark accepted recommendations as CONVERTED
            # Since we don't have local_order_id or order_items mapped here in the simple schema,
            # we'll approximate attribution based on the most recent ACCEPTED rec for the merchant.
            if supabase:
                try:
                    accepted_recos = supabase.table("recommendation_events") \
                        .select("recommendation_id") \
                        .eq("status", "ACCEPTED").execute()
                    
                    for reco in accepted_recos.data:
                        supabase.table("recommendation_events").update({
                            "resulting_order_id": rzp_order_id,
                            "revenue_paise": payment_entity.get("amount", 0),
                            "status": "CONVERTED"
                        }).eq("recommendation_id", reco["recommendation_id"]).execute()
                except Exception as e:
                    logger.error(f"Failed to process revenue attribution: {e}")
            
    elif event == "payment.failed":
        payment_entity = entity.get("payment", {}).get("entity", {})
        rzp_order_id = payment_entity.get("order_id")
        rzp_payment_id = payment_entity.get("id")
        error_desc = payment_entity.get("error_description", "Unknown error")
        
        logger.error(f"Webhook received: Payment failed for order {rzp_order_id} - {error_desc}")
        
        log_agent_action(
            agent_name="Webhook",
            action_type="payment_failed",
            status="REJECTED",
            input_summary=f"Razorpay Order: {rzp_order_id}",
            output_summary=f"Failure reason: {error_desc}",
            razorpay_entity_id=rzp_payment_id
        )

    return {"status": "ok"}
