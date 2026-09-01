import logging
from datetime import datetime, timezone
from utils.supabase_client import supabase
from agents.payment_state import can_transition, is_terminal
from agents.ledger import log_agent_action

logger = logging.getLogger(__name__)

def resolve_payment_status(rzp_order_id: str, rzp_payment_id: str, amount_paise: int, target_status: str, source: str = "webhook") -> dict:
    """
    Authoritative shared pipeline for resolving a payment state and executing fulfillment.
    Called by both Webhooks and check_payment_status (reconciliation).
    
    target_status should be "CAPTURED" or "FAILED".
    """
    now = datetime.now(timezone.utc).isoformat()
    logger.info("Resolving payment status for order %s (payment %s) to %s via %s", rzp_order_id, rzp_payment_id, target_status, source)
    
    # ── Map to intent & local order ──
    # First, try entity mapping for order
    mapping = supabase.table("entity_mapping").select("synthetic_id").eq("entity_type", "order").eq("razorpay_id", rzp_order_id).limit(1).execute()
    order = None
    intent_id = None
    
    if mapping.data:
        order_res = supabase.table("orders").select("*").eq("order_id", mapping.data[0]["synthetic_id"]).maybe_single().execute()
        order = getattr(order_res, "data", None) if order_res is not None else None
        if order:
            intent_id = order.get("purchase_intent_id")
    
    # If mapping missing, try finding intent directly
    if not order:
        intent_res = supabase.table("purchase_intents").select("*").eq("razorpay_order_id", rzp_order_id).maybe_single().execute()
        if intent_res.data:
            intent_id = intent_res.data["purchase_intent_id"]
            
    if not intent_id:
        logger.warning("Unmapped order %s - cannot resolve payment", rzp_order_id)
        return {"status": "ignored", "reason": "unmapped order"}
        
    intent_res = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).maybe_single().execute()
    intent_data = getattr(intent_res, "data", None) if intent_res is not None else None
    if not intent_data:
        return {"status": "ignored", "reason": "intent not found"}

    # ── Amount Validation ──
    expected_amount = int(intent_data.get("amount_paise") or 0)
    if amount_paise != expected_amount:
        logger.error("Amount mismatch: got %d, expected %d for order %s", amount_paise, expected_amount, rzp_order_id)
        return {"status": "error", "reason": "amount mismatch"}
        
    # ── State Validation ──
    current_state = intent_data.get("purchase_state", "PAYMENT_PENDING")
    target_state = "PAYMENT_SUCCESS" if target_status == "CAPTURED" else "PAYMENT_FAILED"
    basket = intent_data.get("basket") or []
    customer_id = intent_data.get("customer_id")
    
    if is_terminal(current_state) and target_state != current_state:
        logger.warning("Blocked state downgrade %s → %s for intent %s", current_state, target_state, intent_id)
        return {"status": "ok", "reason": "terminal state"}
        
    if not can_transition(current_state, target_state):
        logger.info("No-op transition %s → %s for intent %s", current_state, target_state, intent_id)
        return {"status": "ok", "reason": "no-op transition"}

    # ── Order Recovery ──
    # If we have an intent but NO local order mapping (e.g. DB crash during create_razorpay_order)
    # We MUST construct it safely.
    if not order:
        logger.info("Recovering missing local order mapping for intent %s", intent_id)
        order = _recover_local_order(intent_id, rzp_order_id, customer_id, expected_amount, basket, intent_data.get("subtotal_paise", 0), intent_data.get("discount_paise", 0), intent_data.get("tax_paise", 0))
        if not order:
            return {"status": "error", "reason": "order recovery failed"}

    # ── Persist Payment Record ──

    # ── Persist Payment Record ──
    try:
        supabase.table("payments").upsert({
            "payment_id": f"pay_{rzp_payment_id}",
            "order_id": order["order_id"],
            "customer_id": customer_id,
            "amount_paise": amount_paise,
            "currency": "INR",
            "status": target_status,
            "razorpay_payment_id": rzp_payment_id,
            "initiated_at": now,
            "completed_at": now if target_status == "CAPTURED" else None
        }, on_conflict="payment_id").execute()

        supabase.table("entity_mapping").insert({
            "synthetic_id": f"pay_{rzp_payment_id}",
            "entity_type": "payment",
            "razorpay_id": rzp_payment_id
        }).execute()
    except Exception:
        pass # Ignore mapping conflicts

    # ── Fulfillment Pipeline (Atomically Execute Once) ──
    fulfillment_status = "PENDING"
    if target_status == "CAPTURED":
        try:
            rpc_res = supabase.rpc("atomic_inventory_decrement", {
                "p_order_id": order["order_id"],
                "p_intent_id": intent_id,
                "p_items": basket
            }).execute()
            
            status_flag = (rpc_res.data or {}).get("status")
            if status_flag == "success" or status_flag == "already_processed":
                fulfillment_status = "FULFILLED"
                logger.info("Inventory %s for order %s", status_flag, order["order_id"])
            else:
                raise Exception(f"Unexpected RPC status: {status_flag}")
                
        except Exception as e:
            logger.error("Inventory fulfillment failed for order %s: %s", order["order_id"], str(e))
            fulfillment_status = "UNFULFILLED"
            from services.refund_service import initiate_refund
            # Trigger refund workflow asynchronously or synchronously
            initiate_refund(f"pay_{rzp_payment_id}", rzp_payment_id, order["order_id"], customer_id, amount_paise, "Inventory unavailable")

    # ── State Update ──
    # DB-level atomicity: only update if not already in PAYMENT_SUCCESS
    update_res = supabase.table("purchase_intents").update({
        "purchase_state": target_state,
        "razorpay_payment_id": rzp_payment_id,
        "fulfillment_status": fulfillment_status,
        "updated_at": now
    }).eq("purchase_intent_id", intent_id).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    
    if order:
        supabase.table("orders").update({
            "status": target_status,
            "fulfillment_status": fulfillment_status,
            "updated_at": now
        }).eq("order_id", order["order_id"]).neq("status", "CAPTURED").execute()

    if not update_res.data and target_state != "PAYMENT_SUCCESS":
        logger.warning("TOCTOU PREVENTED: Blocked downgrade to %s for %s", target_state, intent_id)
        
    log_agent_action(
        agent_name="Webhook/Reconciliation", action_type="payment.resolved",
        status="SUCCESS" if target_status == "CAPTURED" else "REJECTED",
        input_summary=f"Razorpay order {rzp_order_id}",
        output_summary=f"Payment {target_status} resolved to {fulfillment_status}",
        razorpay_entity_id=rzp_payment_id
    )

    return {"status": "ok", "state": target_state, "fulfillment": fulfillment_status}

def _recover_local_order(intent_id, rzp_order_id, customer_id, expected_amount, basket, subtotal, discount, tax):
    """Deterministically recovers the local order mapping for a Razorpay order ID."""
    import uuid
    # Double check if it was created concurrently
    existing_res = supabase.table("orders").select("*").eq("purchase_intent_id", intent_id).maybe_single().execute()
    existing = getattr(existing_res, "data", None) if existing_res is not None else None
    if existing:
        return existing
        
    local_id = f"ord_{uuid.uuid4().hex[:12]}"
    try:
        supabase.table("orders").insert({
            "order_id": local_id,
            "purchase_intent_id": intent_id,
            "merchant_id": "merchant_mxx_001",
            "customer_id": customer_id,
            "status": "CREATED",
            "subtotal_paise": subtotal,
            "discount_paise": discount,
            "tax_paise": tax,
            "total_paise": expected_amount,
            "currency": "INR",
            "source": "RECOVERY",
            "purchase_state": "PAYMENT_PENDING"
        }).execute()
        
        for entry in basket:
            supabase.table("order_items").insert({
                "order_item_id": f"oi_{uuid.uuid4().hex[:12]}",
                "order_id": local_id,
                "product_id": entry["product_id"],
                "quantity": int(entry.get("quantity", 1)),
                "unit_price_paise": 0, 
                "discount_paise": 0,
                "total_paise": 0
            }).execute()
            
        supabase.table("entity_mapping").insert({
            "synthetic_id": local_id,
            "entity_type": "order",
            "razorpay_id": rzp_order_id
        }).execute()
        
        logger.info("Successfully recovered local order %s", local_id)
        return {"order_id": local_id, "customer_id": customer_id}
    except Exception as e:
        logger.error("Failed to recover local order for intent %s: %s", intent_id, e)
        return None
