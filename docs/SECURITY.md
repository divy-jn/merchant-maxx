# Security & Hardening: Merchant MAXX

## Auth & Authorization
- **JWT Based Auth**: Implemented in `routes/auth.py` and `middleware/auth_middleware.py`.
- **Stateless Verification**: The backend validates JWTs without needing a database lookup for every request.

## Row Level Security (RLS) & IDOR Protections
- **Supabase RLS**: Policies enforce that users can only read/write their own `purchase_intents`, `conversations`, and `messages`.
- **IDOR Prevention**: All API routes referencing sensitive resources validate ownership against the `user_id` decoded from the JWT.

## Credential Handling & Secrets Policy
- **Never Commit Secrets**: `RAZORPAY_KEY_SECRET`, `SUPABASE_ANON_KEY`, and LLM API keys must remain in environment variables or Secret Manager.
- Scrubbed history guarantees no exposed credentials exist in the Git log.

## Guardian Policy Enforcement
The Guardian agent acts as a constitutional AI firewall. Key deterministic rules:
- **RULE_06**: `create_razorpay_order` can ONLY execute if the server-side state is strictly `USER_CONFIRMED`.
- **RULE_08**: Blocks blind LLM retries on failed payment links.

## Payment Idempotency & Webhook Verification
- **Order Idempotency**: `purchase_intent_id` maps safely to synthetic `ord_*` identifiers and subsequently to Razorpay `order_*` IDs.
- **Webhook Verification**: All webhooks hitting `routes/webhooks.py` validate the Razorpay cryptographic signature before processing `payment.captured` or `payment.failed`.

## Inventory Atomic Locks (Ghost Order Prevention)
- **Time-Of-Check to Time-Of-Use (TOCTOU) Mitigation**: Inventory is decremented atomically in Supabase via an RPC `atomic_inventory_decrement` during the webhook fulfillment phase, not during cart building.
- Duplicate webhooks are ignored using `order_id` as an idempotency key in `inventory_decrement_events`.

## Safe Error Handling
- `GlobalErrorMiddleware` catches unhandled exceptions to prevent stack trace leakage.
- AI hallucinations (e.g., negative quantities, malicious product IDs) are caught by strict Pydantic schemas and Python type bounds checking.
