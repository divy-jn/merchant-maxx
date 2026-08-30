# Task 23: Razorpay Event/Webhook Architecture Audit & Hardening

## Overview
This document summarizes the findings and fixes implemented to secure Merchant Maxx's webhook architecture. We audited the idempotency logic, race conditions, mapping failures, and state transitions to ensure that the payment lifecycle is robust and consistent.

## Invariants Proven
- **No Orphaned Payments:** `create_razorpay_order` guarantees that a payment link is only delivered to the customer if the local order and entity mapping are successfully persisted. If persistence fails, the order creation aborts safely.
- **Strict State Locking (TOCTOU Prevention):** Webhooks use an atomic conditional update (`.neq("purchase_state", "PAYMENT_SUCCESS")`) to prevent an out-of-order `payment.failed` event from overwriting a successful payment state.
- **Fallback Resolution:** Webhooks can gracefully recover an order's intent state even if the local `orders` mapping was somehow deleted or failed, using the `purchase_intents.razorpay_order_id` fallback.
- **Idempotency Preserved:** Razorpay webhook events are tracked using `webhook_events`, guaranteeing exactly-once processing for each unique `event_id`. Non-payment events (e.g., refunds, disputes) are appropriately ignored from the main state machine.

## Webhook Architecture Matrix
The table below maps the incoming Razorpay event, the validations performed, the resulting target state, and the exact database mutations.

| Incoming Event | Validation Criteria | Target State | Database Mutations |
|-----------------|---------------------|--------------|---------------------|
| `payment.authorized` | - Verify webhook signature.<br>- Verify local order or intent exists.<br>- Verify amount matches `total_paise` exactly. | `PAYMENT_PENDING` (implicit) | 1. `webhook_events` updated to `PROCESSED`.<br>2. Logs agent action `SUCCESS`. No intent transition is made since it awaits capture. |
| `payment.captured` / `order.paid` | - Verify webhook signature.<br>- Verify local order or intent exists.<br>- Verify amount matches `total_paise` exactly. | `PAYMENT_SUCCESS` | 1. `payments` table upserted with status `CAPTURED`.<br>2. `entity_mapping` inserted.<br>3. `purchase_intents` atomically updated to `PAYMENT_SUCCESS`.<br>4. `recommendation_events` marked as `CONVERTED`. |
| `payment.failed` | - Verify webhook signature.<br>- Verify local order or intent exists.<br>- Verify amount matches `total_paise` exactly. | `PAYMENT_FAILED` | 1. `payments` table upserted with status `FAILED`.<br>2. `entity_mapping` inserted.<br>3. `purchase_intents` atomically updated to `PAYMENT_FAILED` **ONLY IF** current state != `PAYMENT_SUCCESS`. |
| Other Events (e.g., `refund.created`) | - Unrecognized by the primary state machine. | None (`IGNORED`) | 1. `webhook_events` updated to `IGNORED`. No state mutation occurs. |

## Concurrency Tests Implemented
- `test_webhook_toctou_race_condition`: Proves that a simulated `payment.failed` event executing concurrently slightly behind `order.paid` will not downgrade `PAYMENT_SUCCESS` to `PAYMENT_FAILED`.
- `test_create_razorpay_order_fails_if_local_persistence_fails`: Proves that if the database mapping logic errors out, `create_razorpay_order` returns an internal error rather than falsely succeeding with an unmapped Razorpay Order.
- `test_webhook_fallback_to_intent_id_without_entity_mapping`: Proves that a webhook without an `orders` or `entity_mapping` row can still correctly finalize the `purchase_intents` state.
