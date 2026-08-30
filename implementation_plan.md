# Task 23: Razorpay Event/Webhook Architecture Audit

## Goal
Audit the webhook and event architecture for Merchant Maxx, focusing on idempotency, race conditions, mapping failures, and state transitions.

## Findings & Flaws Discovered

After reviewing `backend/routes/webhooks.py` and `backend/agents/tools.py`, I have identified two critical (P0) architectural flaws:

### 1. TOCTOU Race Condition in Webhook State Updates
**The Flaw**: `webhooks.py` reads the current `purchase_state` via a `select()` query, validates the transition (preventing downgrades like `PAYMENT_SUCCESS` → `PAYMENT_FAILED`), and then blindly executes an `update()`.
If Razorpay delivers an `order.paid` (success) and a delayed `payment.failed` webhook simultaneously, both might read `PAYMENT_PENDING` at the same time. The delayed `payment.failed` webhook could execute its `update()` last, overwriting the successful payment and leaving the database in a `PAYMENT_FAILED` state despite the customer having paid.
**The Fix**: The `update()` must be atomic, enforcing the transition rule within the query itself, e.g.:
```python
supabase.table("purchase_intents").update({"purchase_state": target_state}) \
    .eq("purchase_intent_id", intent_id) \
    .neq("purchase_state", "PAYMENT_SUCCESS") \
    .execute()
```

### 2. Silent Failure of Local Order Mapping leads to Orphaned Payments
**The Flaw**: In `tools.py` (`create_razorpay_order`), after reserving the intent and successfully creating the order via the Razorpay API, the system attempts to insert rows into `orders`, `order_items`, and `entity_mapping`. If this database insertion fails (e.g. network timeout), it catches the exception, logs a warning, and **returns SUCCESS to the agent**.
Because `entity_mapping` is missing, when the customer pays and the webhook arrives, `_local_order(rzp_order_id)` will fail to find the order. The webhook will return `{"status": "ignored", "reason": "unmapped order"}` and permanently drop the payment event.
**The Fix**: If local order mapping fails, we must return an error to the LLM instead of success. An orphaned Razorpay order (where the user never receives the checkout link) is perfectly safe and will simply expire, whereas returning success for an unmapped order guarantees a dropped payment.

## Proposed Changes

### [backend/routes/webhooks.py]
- **[MODIFY]** `handle_razorpay_webhook`: Make the `purchase_intents` state update atomic. We will enforce that a terminal state (like `PAYMENT_SUCCESS`) cannot be overwritten by combining the update with a `.neq("purchase_state", "PAYMENT_SUCCESS")` condition (or similar).
- **[MODIFY]** `handle_razorpay_webhook`: Enhance `_local_order` to fallback to `purchase_intents.razorpay_order_id` if `entity_mapping` is missing, ensuring we at least capture the state transition for the intent even if the `orders` table is corrupted.

### [backend/agents/tools.py]
- **[MODIFY]** `create_razorpay_order`: If the `orders` or `entity_mapping` insertion fails, we will raise an exception or return an error to the agent, refusing to provide a checkout link for a corrupted state.

## User Review Required
> [!IMPORTANT]
> The TOCTOU race in the webhook is a classic concurrency vulnerability that can cause paid orders to reflect as failed. Do you approve the proposed atomic `.neq()` guard in `webhooks.py` and the strict failure handling in `tools.py`?
