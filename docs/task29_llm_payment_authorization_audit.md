# Task 29: LLM Payment Authorization Bypass Remediation

## Phase 0: Read-Only Audit

### 1. Current Vulnerability
The core vulnerability is that payment authorization is not strictly and cryptographically tied to the exact basket the user confirmed. Additionally, the payment tool (`create_razorpay_order`) lacks explicit IDOR checks for the intent against the current user context, and it bypasses `Guardian` validation by hardcoding confirmation metadata.

### 2. Exact Attack Path
1. **Chat Route TOCTOU**: A user types "Yes, I confirm, but actually add a second laptop."
2. `chat.py` regex-matches "Yes" and updates the intent to `USER_CONFIRMED`.
3. The LLM receives the message and invokes both `stage_purchase_intent` (changing the basket) and `create_razorpay_order` (creating the payment).
4. Depending on race conditions, `create_razorpay_order` might authorize the old basket or the new basket, or fail unpredictably.
5. **IDOR via Direct Tool Invocation**: If another tool or direct LangGraph invocation is made, `create_razorpay_order` fetches the `purchase_intent_id` from context but fails to verify that `intent["conversation_id"] == state["session_id"]`.
6. **Guardian Bypass**: `create_razorpay_order` explicitly passes `{"user_confirmed": True, "purchase_state": "USER_CONFIRMED"}` to `Guardian.validate_action()`, effectively lying to the guardian agent and bypassing independent LLM-based verification.

### 3. Relevant Files/Functions
- `backend/agents/tools.py`: `create_razorpay_order`, `stage_purchase_intent`
- `backend/routes/chat.py`: Regex confirmation logic
- `backend/db/migrations/006_basket_confirmation.sql` (to be created): Must add `confirmed_basket` and `confirmed_amount_paise`.

### 4. Current Confirmation Source
- **Regex matching** in `backend/routes/chat.py` sets `user_confirmed = True`.
- No snapshot of *what* was confirmed is taken.

### 5. Authoritative Confirmation Source (Proposed)
- `purchase_intents.confirmed_basket` (JSONB)
- `purchase_intents.confirmed_amount_paise` (INT)
- `purchase_intents.confirmation_timestamp` (TIMESTAMPTZ)
When the user confirms, the current basket and amount are snapshotted into these fields.

### 6. Proposed Invariant
`create_razorpay_order` MUST verify:
1. `purchase_intents.user_confirmed == True`
2. `purchase_intents.purchase_state == 'USER_CONFIRMED'`
3. `purchase_intents.basket == purchase_intents.confirmed_basket`
4. `server_calculated_total == purchase_intents.confirmed_amount_paise`
5. `purchase_intents.conversation_id == state.session_id`

### 7. Proposed Remediation
1. **Schema Update**: Add confirmation snapshot fields to `purchase_intents`.
2. **chat.py**: Snapshot the basket and amount when matching `CONFIRM_RE`.
3. **scout.py**: When modifying the basket, automatically clear `confirmed_basket` and `confirmed_amount_paise` along with setting `user_confirmed = False`.
4. **tools.py**: Implement the rigorous invariants in `create_razorpay_order`.
5. **Guardian**: Pass the *actual* DB state to Guardian instead of hardcoded `True`.

### 8. Test Strategy
Implement 12 adversarial test cases in `backend/tests/test_llm_payment_authorization.py` as outlined in the prompt, focusing specifically on race conditions, basket mutations post-confirmation, and IDOR.
