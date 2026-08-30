# Task 22: Atomic Payment State Locking

## Overview
This report documents the resolution of the P0 TOCTOU (Time-Of-Check to Time-Of-Use) race condition identified in Task 21. Prior to this fix, it was possible for the Scout agent to mutate a `purchase_intent`'s basket while the Closer agent was concurrently negotiating a payment with Razorpay. This led to a mismatch between the authoritative DB state and the external payment state.

## Solution Implemented
We implemented an atomic locking mechanism at the database level to guarantee payment integrity.

1. **State Machine Locking**: We introduced the `ORDER_CREATING` state. When `create_razorpay_order` is invoked, it atomically transitions the intent from `USER_CONFIRMED` to `ORDER_CREATING`.
2. **Scout Concurrency Guards**: We updated `scout_node` to rely on the PostgREST Python client's `.is_("razorpay_order_id", "null")` method combined with an `.in_()` clause for unlocked states. If Scout attempts a mutation while the intent is locked, the atomic update modifies 0 rows, which correctly triggers the creation of a "cloned" `purchase_intent` without corrupting the locked state.
3. **Database Schema Enforcement**: We removed non-existent columns (`subtotal_paise`, `tax_paise`, `discount_paise`) from the `scout.py` mutations which previously caused the query to throw exceptions, thus skipping the safe fallback logic.
4. **Test Infrastructure**: We corrected the `test_atomic_payment_locking.py` testing framework to invoke `scout_node(state)` with a mock LLM to guarantee realistic testing of the DB integration path.

## Ghost Order Semantics & Recovery
If the server crashes while in `ORDER_CREATING` (or Razorpay returns a 5xx error), the intent is stuck in `ORDER_CREATING` with `razorpay_order_id = NULL`.
To recover, the Guardian exception block automatically transitions the state back to `USER_CONFIRMED` if the Razorpay API creation fails, leaving the intent available for retry without generating ghost orders in the DB.

## Conclusion
The atomic TOCTOU issue is fixed, preventing Scout from mutating baskets that are engaged in Razorpay payment flows.
