# Task 24: Cross-Layer Production Architecture Audit

This document presents the findings from a read-only deep audit of the Merchant Maxx repository across the frontend, API, LangGraph, tool, and database layers.

## 🔴 P0 Critical Security Vulnerabilities

### 1. Hardcoded JWT Secret in Production
- **Location:** `backend/config.py` & `.env`
- **Issue:** The `JWT_SECRET` defaults to `"merchant-maxx-secret-key-change-in-prod"`. It is not overridden in `.env` nor injected into the Cloud Run container environment.
- **Impact:** Any attacker can trivially forge a valid JWT to authenticate as any user (including merchants) by signing a token with the default secret.
- **Fix:** Inject a secure, randomized `JWT_SECRET` into the Cloud Run environment and remove the insecure default from `config.py`.

### 2. Insecure Direct Object Reference (IDOR) on Conversation ID
- **Location:** `backend/routes/chat.py` (`chat_with_maxx`, `get_chat_history`, `clear_chat_history`)
- **Issue:** The API accepts `conversation_id` from the client and queries Supabase directly without verifying if the conversation belongs to the `current_user`.
- **Impact:** An unauthenticated user (or any authenticated user) can read chat history, forge messages, and manipulate the purchase state of *any* other user's session if they obtain the UUID.
- **Fix:** Enforce authorization: verify `user_id == current_user.user_id` when fetching/mutating conversations for authenticated users.

---

## 🟠 P1 Data Integrity & Concurrency Bugs

### 3. Infinite Inventory (Overselling) Bug
- **Location:** `backend/agents/tools.py` (`create_razorpay_order`) & `backend/routes/webhooks.py`
- **Issue:** While `create_razorpay_order` correctly *validates* that `inventory_qty >= quantity`, no code in the entire repository ever *decrements* the `inventory_qty`.
- **Impact:** Products can be oversold infinitely.
- **Fix:** Add an atomic inventory decrement operation in `webhooks.py` upon `PAYMENT_SUCCESS`, or in a dedicated `inventory` service hooked into the order fulfillment lifecycle.

### 4. Missing Database Table Definition (`webhook_events`)
- **Location:** `backend/db/schema.sql` & `backend/db/migrations/`
- **Issue:** `webhook_events` is used extensively in `webhooks.py` for idempotency, but its `CREATE TABLE` definition is completely missing from `schema.sql`.
- **Impact:** Fresh deployments (or DB resets) will result in broken webhooks because the table does not exist. The application currently relies on unversioned, manual schema drift in Supabase.
- **Fix:** Add `CREATE TABLE webhook_events` to `schema.sql` and the migrations directory.

### 5. State Downgrade TOCTOU in Merger Node
- **Location:** `backend/agents/merger.py`
- **Issue:** The Merger node blindly updates `purchase_state` using `supabase.table("purchase_intents").update({"purchase_state": next_state})`. It does not use conditional updates (`.neq("purchase_state", "PAYMENT_SUCCESS")`).
- **Impact:** If a webhook updates the DB to `PAYMENT_SUCCESS` concurrently while `merger_node` is processing a turn, Merger will blindly overwrite the state back to `PRODUCT_SELECTED`, destroying payment finality.
- **Fix:** Use atomic conditional updates in `merger.py` when syncing the `next_state` to the DB.

### 6. State Downgrade TOCTOU in `check_payment_status` Tool
- **Location:** `backend/agents/tools.py`
- **Issue:** The tool reads `db_state`, pauses to make a network call to Razorpay, and then unconditionally updates the DB if Razorpay returns "captured". It does not verify if the DB state changed to `PAYMENT_FAILED` concurrently via a webhook during the network delay.
- **Impact:** It can resurrect a failed intent into a success state out-of-band.
- **Fix:** Add `.neq("purchase_state", "PAYMENT_FAILED")` and use DB-level atomicity when applying the reconciliation.

---

## 🟡 P2 UX & Logic Flaws

### 7. Permanent Stale Price Blockade
- **Location:** `backend/agents/tools.py` (`create_razorpay_order`)
- **Issue:** If a product's price changes in the DB after an intent is staged but before it is confirmed, `create_razorpay_order` blocks the order: *"Order blocked by Guardian: server-calculated basket total does not match purchase intent"*.
- **Impact:** The intent gets permanently stuck in `USER_CONFIRMED`. Scout won't restage it because it's confirmed, and Closer refuses to proceed. The user cannot recover without manually clearing the cart.
- **Fix:** The tool (or Guardian) should automatically mutate the intent with the new authoritative price and revert the state back to `PRODUCT_SELECTED`, asking the user to re-confirm the updated total.

---

## 🔵 P3 Architecture & Code Hygiene

### 8. Tool Call Leakage (Redundant Execution)
- **Location:** `backend/agents/scout.py` & `backend/agents/maxx.py`
- **Issue:** `scout_node` intercepts and processes `stage_purchase_intent` internally (updating Supabase directly). However, it leaves the tool call attached to the AIMessage. LangGraph then routes to `ToolNode`, which executes the dummy function in `tools.py`.
- **Impact:** Duplicate processing, cluttered conversation history, and unnecessary graph cycles.
- **Fix:** If Scout handles the tool server-side, it should either strip the tool call from the AIMessage or rely completely on the standard `ToolNode` architecture instead of side-stepping it.

---

## Recommended Next Steps

We recommend executing a multi-phase remediation plan:

1. **Security Patch (Immediate)**: Fix the P0 JWT and IDOR vulnerabilities.
2. **Data Integrity Patch**: Introduce the `webhook_events` schema definition and implement atomic inventory decrements.
3. **Concurrency Hardening**: Fix the blind DB updates in `merger.py` and `tools.py`.
4. **UX / Flow Recovery**: Implement safe cart re-pricing.
