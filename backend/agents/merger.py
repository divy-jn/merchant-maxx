import logging
from .payment_state import can_transition
from utils.supabase_client import supabase

logger = logging.getLogger(__name__)

def merger_node(state: dict):
    """
    Merger / Validator node.
    Synchronizes state from Scout and Booster.
    Applies deterministic payment state transitions.

    INVARIANT: Scout is authoritative for purchase product/basket.
    Booster is advisory only — it cannot change the purchase product.
    """
    import time
    merger_start = time.time()
    
    state_update = {}
    current_state = state.get("purchase_state", "IDLE")
    ctx = state.get("purchase_context") or {}
    scout_res = state.get("scout_result") or {}
    booster_res = state.get("booster_result") or {}

    next_state = current_state

    # 1. Apply Scout's intent staging if it happened
    if scout_res.get("intent_staged") and current_state == "IDLE":
        if can_transition(current_state, "PRODUCT_SELECTED"):
            next_state = "PRODUCT_SELECTED"
            ctx = scout_res.get("product_context", ctx)
            state_update["purchase_context"] = ctx
            state_update["user_confirmed"] = False

    # 2. Booster conflict detection: Booster must NOT override Scout's products
    #    Booster result may contain a recommended product_id, but it is advisory.
    #    If Booster somehow tried to stage a different product, we log and ignore.
    scout_product_ids = [item.get("product_id") for item in ctx.get("basket_items", [])]
    
    booster_product = booster_res.get("product_id")  # Not normally set, but guard anyway
    if booster_product and scout_product_ids and booster_product not in scout_product_ids:
        logger.warning(
            "Merger conflict: Booster tried to set product %s but Scout's authoritative products are %s — ignoring Booster product",
            booster_product, scout_product_ids
        )
        # Do NOT apply Booster's product override

    # 3. Apply Booster's recommendation status if it succeeded
    if next_state == "PRODUCT_SELECTED":
        if booster_res.get("recommendations_shown"):
            if can_transition(next_state, "RECOMMENDATION_SHOWN"):
                next_state = "RECOMMENDATION_SHOWN"
        elif booster_res.get("status") in {"success", "unavailable", "skipped"}:
            # If booster finished (with or without recs) or failed, move to PURCHASE_PENDING
            if can_transition(next_state, "PURCHASE_PENDING"):
                next_state = "PURCHASE_PENDING"

    # 4. Ensure we don't downgrade PAYMENT_SUCCESS blindly
    if current_state == "PAYMENT_SUCCESS" and next_state != "PAYMENT_SUCCESS":
        logger.warning("Merger prevented downgrade from PAYMENT_SUCCESS to %s", next_state)
        next_state = "PAYMENT_SUCCESS"

    if next_state != current_state:
        state_update["purchase_state"] = next_state
        if ctx.get("purchase_intent_id") and supabase:
            try:
                res = supabase.table("purchase_intents").update({
                    "purchase_state": next_state
                }).eq("purchase_intent_id", ctx["purchase_intent_id"]).in_("purchase_state", ["IDLE", "PRODUCT_SELECTED", "RECOMMENDATION_SHOWN", "PURCHASE_PENDING", "RECOVERY_PENDING"]).execute()
                
                if not res.data:
                    logger.warning("Merger atomic update failed for intent %s (likely advanced by webhook or locked).", ctx["purchase_intent_id"])
            except Exception as e:
                logger.error("Merger failed to sync state to DB: %s", e)

    # Telemetry for concurrency proof
    state_update["merger_start"] = merger_start
    
    # Clear the results so they don't pollute the next turn
    state_update["scout_result"] = {}
    state_update["booster_result"] = {}
    
    return state_update

