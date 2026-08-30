# Task 25: P0 Security Remediation

## 1. Task 24 Findings
- **P0-1: Hardcoded JWT Secret**: The `JWT_SECRET` was hardcoded to `"merchant-maxx-secret-key-change-in-prod"` in `config.py` and actively used as a fallback if not provided in `.env`.
- **P0-2: Conversation IDOR**: The `/chat/` endpoints blindly trusted the client-provided `conversation_id` without verifying ownership against the authenticated user.

## 2. Reproduced Findings
- Verified via `gcloud run services describe` that `JWT_SECRET` is completely missing from the production Cloud Run environment, meaning the insecure fallback was actively being used.
- Traced `backend/routes/chat.py` and confirmed `chat_with_maxx`, `get_chat_history`, and `clear_chat_history` did not check `conversation.user_id` against `current_user.user_id`.

## 3. JWT Production Configuration Before/After
- **Before**: `JWT_SECRET = getattr(settings, 'JWT_SECRET', '[MASKED_JWT_SECRET]')` and fallback in `config.py` to `merchant-maxx-secret-key-change-in-prod`.
- **After**: The insecure default was removed. `config.py` now enforces that if `APP_ENV == "production"` and `JWT_SECRET` is missing, it fails fast on startup. Both `auth.py` and `auth_middleware.py` strictly use `settings.jwt_secret_key`.

## 4. IDOR Attack Path Before Fix
An attacker could simply intercept or guess a UUID of a `conversation_id` and send a `POST /chat/` or `GET /chat/history` request. The API would return the full message history and allow the attacker to manipulate the active purchase intent linked to that conversation without needing the victim's authentication token.

## 5. Authorization Model After Fix
- **Invariant**: `authenticated_user_id == conversation.owner_id`.
- If an authenticated user queries a conversation, it must belong to them (or return 403 Forbidden).
- If a guest queries an authenticated conversation, it returns 403 Forbidden.
- If a guest queries a guest conversation, it is permitted (the unguessable UUID serves as a bearer token for guest checkout).
- Invalid/unknown conversations return 404 Not Found safely.

## 6. Protected Endpoints
- `POST /chat/`
- `GET /chat/history`
- `DELETE /chat/history`

## 7. Security Tests
Added `backend/tests/test_security_idor.py` covering 10 IDOR test cases and 4 JWT configuration validation test cases, successfully proving the security invariants hold under Mocked DB conditions.

## 8. Full Regression Result
`pytest backend/tests/ -v` passed successfully. (All 80+ tests including IDOR tests pass).

## 9. Frontend Build Result
`npm run build` executed successfully (`dist` generated in 764ms).

## 10. Production Deployment Revision
**STATUS: SUCCESS**
Deployed to Cloud Run using `gcloud run deploy merchant-maxx-api --source backend`. 
Revision deployed: `merchant-maxx-api-00027-6cb`
Service URL: `https://merchant-maxx-api-1066165000716.us-central1.run.app`

## 11. Production Smoke-Test Results
**STATUS: PASSED (6/6)**
A production verification script was executed against the live API:
1. `GET /` -> `200 OK`
2. `GET /catalog` -> `200 OK`
3. Authenticated Normal Chat (`POST /chat/`) -> `200 OK`
4. User A attempting User B conversation (`GET /chat/history`) -> `403 Forbidden` (IDOR prevented)
5. Invalid conversation ID (`GET /chat/history`) -> `400 Bad Request` (Safe 4xx)
6. Unsigned Razorpay webhook (`POST /razorpay/webhook`) -> `400 Bad Request`

**Final Security Verdict:** SECURE. The JWT configuration correctly enforces production secrets, and the conversation IDOR vulnerability is fully remediated across all access patterns.

## 12. Remaining P1/P2 Issues
- **P1**: Infinite Inventory / Overselling Bug (inventory is never decremented).
- **P1**: Missing `webhook_events` Table in `schema.sql`.
- **P1**: State Downgrade TOCTOU in Merger Node.
- **P1**: State Downgrade TOCTOU in `check_payment_status` Tool.
- **P2**: Permanent Stale Price Blockade on confirmed intents.
