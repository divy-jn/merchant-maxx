# TASK 29: LLM Payment Authorization Bypass Remediation

## Vulnerability Overview

A P0 vulnerability was identified during Task 27 testing where the LLM (Closer agent) could invoke the `create_razorpay_order` tool and directly claim `user_confirmed = True` without cryptographic or server-side proof that the user actually confirmed the specific basket and amount.

This meant the LLM could unilaterally authorize payments, violating the core security invariant that "The LLM can request payment creation, but the LLM must never authorize payment."

## Remediation Architecture

The system has been refactored to enforce that the database (`purchase_intents` table) is the sole authority for payment authorization. 

### 1. Atomic Confirmation Snapshots
When a user explicitly confirms a purchase intent, the `confirm_purchase_intent` route now atomically snapshots:
- `confirmed_basket`
- `confirmed_amount_paise`
- `confirmation_timestamp`
- `user_confirmed = True`

This immutable snapshot acts as the cryptographic proof of the user's intent at the exact moment of confirmation.

### 2. Independent Server-Side Verification
The `create_razorpay_order` tool no longer trusts the LLM's arguments. When invoked, it:
1. Re-fetches the `purchase_intent` from the database.
2. Verifies `user_confirmed == True`.
3. Validates that the current basket exactly matches the `confirmed_basket`.
4. Validates that the current server-calculated amount exactly matches the `confirmed_amount_paise`.
5. Verifies ownership (`conversation_id` matches the current authenticated session).

### 3. Atomic Locking and Race Condition Prevention
To prevent Time-of-Check to Time-of-Use (TOCTOU) race conditions where the basket is modified *during* order creation:
- An intermediate `ORDER_CREATING` lock state was introduced.
- `create_razorpay_order` atomically transitions the intent from `USER_CONFIRMED` to `ORDER_CREATING`.
- If the Scout agent attempts to modify a locked intent, the atomic update fails safely. Scout then clones the intent into a new, unlocked `pi_*` intent and applies the changes there, preserving the locked intent for the in-progress order.
- The `ORDER_CREATING` state acts as a mutex for both Razorpay API calls and database mutations.

## Verification

The test suite in `backend/tests/test_atomic_payment_locking.py` and `backend/tests/test_payment_integrity.py` validates the following adversarial scenarios:
- **TOCTOU Race Condition**: Simulates concurrent modification during order creation.
- **Normal Mutation**: Validates unlocked intents are still mutated in place.
- **Cloning on Lock**: Validates locked intents are cloned on mutation.
- **API Failure Rollback**: Validates failures in the Razorpay API gracefully rollback the state to `USER_CONFIRMED`.
- **Idempotency**: Validates Guardian correctly blocks duplicate order creations.

All regression and adversarial tests are currently passing.

## Production Deployment & Verification

Task 29 changes have been successfully deployed to the `merchant-maxx-api` Cloud Run service.

**Revision:** `merchant-maxx-api-00033-hd7` serving 100% of traffic.

**Production Smoke Tests Results:**
- ✅ `GET /`: Returns 200 OK
- ✅ `GET /catalog`: Returns 200 OK (Cache hits verified)
- ✅ Authenticated Chat: Successfully processes messages (DB connection functioning properly)
- ✅ Cross-user conversation access: Returns 403 Forbidden
- ✅ Unsigned Razorpay webhook: Returns 400 Bad Request (Invalid signature)
- ✅ Supabase DB access: Backend retains full connectivity to the DB following migration `006_basket_confirmation.sql`.

**Final Security Sign-off:**
The critical invariant "THE LLM CAN REQUEST PAYMENT CREATION, BUT THE LLM MUST NEVER AUTHORIZE PAYMENT" has been successfully achieved and deployed to production. The database serves as the absolute authority, enforcing atomicity for purchase intents.

Task 29 is now COMPLETE.
