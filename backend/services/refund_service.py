import logging
from datetime import datetime, timezone
from utils.supabase_client import supabase
from config import settings

logger = logging.getLogger(__name__)

def rzp_refund(razorpay_payment_id: str, amount_paise: int, notes: dict) -> dict:
    """Mockable Razorpay refund API wrapper."""
    from razorpay_service.client import rzp
    # In tests, rzp is mocked. In production, this hits Razorpay.
    return rzp.payment.refund(razorpay_payment_id, amount_paise, {"notes": notes})

def initiate_refund(payment_id: str, razorpay_payment_id: str, order_id: str, customer_id: str, amount_paise: int, reason: str = "fulfillment_failure") -> dict:
    """
    Authoritative refund pipeline with strict idempotency and DB safety.
    """
    import uuid
    now = datetime.now(timezone.utc).isoformat()
    
    # Contextual idempotency key: 1 refund per payment per reason context
    # Usually you only ever refund a payment once, so payment_id is the key.
    idempotency_key = f"refund_{payment_id}"
    refund_id = f"ref_{uuid.uuid4().hex[:12]}"
    
    logger.info("Initiating refund for payment %s, amount %d, reason: %s", payment_id, amount_paise, reason)
    
    # 1. Claim the refund atomically in the DB
    try:
        supabase.table("refunds").insert({
            "refund_id": refund_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount_paise": amount_paise,
            "status": "REFUND_PENDING",
            "reason": reason,
            "idempotency_key": idempotency_key,
            "created_at": now
        }).execute()
    except Exception as e:
        # Check if it was a unique constraint violation (idempotency key)
        if "duplicate key" in str(e) or "unique constraint" in str(e).lower() or "23505" in str(e):
            logger.info("Refund idempotency caught: refund already exists for %s", idempotency_key)
            existing = (lambda r: getattr(r, "data", None))(supabase.table("refunds").select("*").eq("idempotency_key", idempotency_key).maybe_single().execute())
            if existing:
                return {"status": existing.get("status"), "refund_id": existing.get("refund_id")}
        
        logger.error("Failed to insert refund claim for %s: %s", payment_id, e)
        return {"status": "REFUND_FAILED", "error": "database_error"}
        
    # 2. Call Razorpay
    try:
        # We transition to REQUESTED to indicate we are making the external call.
        # If we crash here, the DB remains in REQUESTED. Reconciliation can recover it.
        supabase.table("refunds").update({
            "status": "REFUND_REQUESTED",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("refund_id", refund_id).execute()
        
        notes = {"order_id": order_id, "reason": reason}
        rzp_res = rzp_refund(razorpay_payment_id, amount_paise, notes)
        
        rzp_refund_id = rzp_res.get("id")
        
        # 3. Persist Success
        supabase.table("refunds").update({
            "status": "REFUNDED",
            "razorpay_refund_id": rzp_refund_id,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("refund_id", refund_id).execute()
        
        logger.info("Refund successful: %s -> %s", refund_id, rzp_refund_id)
        return {"status": "REFUNDED", "refund_id": refund_id, "razorpay_refund_id": rzp_refund_id}
        
    except Exception as api_err:
        logger.error("Razorpay refund API failed for %s: %s", payment_id, api_err)
        # Timeout/Connection error could mean Razorpay accepted it, we just didn't get the response!
        # Do not mark as FAILED unless it's a confirmed 4xx from Razorpay.
        # Mark as UNKNOWN so reconciliation can check it later.
        supabase.table("refunds").update({
            "status": "REFUND_UNKNOWN",
            "error_reason": str(api_err),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("refund_id", refund_id).execute()
        
        return {"status": "REFUND_UNKNOWN", "refund_id": refund_id}

def check_refund_status(refund_id: str) -> dict:
    """Reconcile an UNKNOWN refund by querying Razorpay."""
    ref = (lambda r: getattr(r, "data", None))(supabase.table("refunds").select("*").eq("refund_id", refund_id).maybe_single().execute())
    if not ref:
        return {"status": "error", "reason": "not_found"}
        
    if ref["status"] == "REFUNDED":
        return {"status": "REFUNDED"}
        
    razorpay_payment_id = ref.get("razorpay_payment_id")
    if not razorpay_payment_id:
        # If we didn't save it, we must derive it
        payment = (lambda r: getattr(r, "data", None))(supabase.table("payments").select("razorpay_payment_id").eq("payment_id", ref["payment_id"]).maybe_single().execute())
        if payment:
            razorpay_payment_id = payment.get("razorpay_payment_id")
            
    if not razorpay_payment_id:
        return {"status": "error", "reason": "missing_rzp_payment_id"}
        
    try:
        from razorpay_service.client import rzp
        # Fetch refunds for the payment
        refunds = rzp.payment.refunds(razorpay_payment_id).get("items", [])
        # Look for a refund matching the amount
        found = False
        rzp_ref_id = None
        for r in refunds:
            if r.get("amount") == ref["amount_paise"]:
                # In production, we'd also check notes for our ID
                found = True
                rzp_ref_id = r.get("id")
                break
                
        if found:
            supabase.table("refunds").update({
                "status": "REFUNDED",
                "razorpay_refund_id": rzp_ref_id,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("refund_id", refund_id).neq("status", "REFUNDED").execute()
            return {"status": "REFUNDED"}
        else:
            # Not found on Razorpay. We can safely retry.
            return {"status": "NOT_FOUND"}
            
    except Exception as e:
        logger.error("Failed to reconcile refund %s: %s", refund_id, e)
        return {"status": "UNKNOWN"}
