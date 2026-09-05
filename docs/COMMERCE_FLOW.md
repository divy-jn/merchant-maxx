# Commerce Flow: Merchant MAXX

## End-to-End Customer Shopping Flow
1. **Discovery**: Customer expresses interest (e.g., "I need a gaming laptop").
2. **Search**: MAXX delegates to `Scout`, which searches Pinecone and retrieves products.
3. **Cart Assembly**: `Scout` adds items to the `purchase_intents` table (basket) using strict ADD vs SET quantity semantics.
4. **Confirmation**: `Closer` asks for final confirmation. The user types "Yes, buy it."
5. **State Transition**: The intent moves to `USER_CONFIRMED` in Supabase.
6. **Execution**: `Guardian` validates the `USER_CONFIRMED` state and allows `Closer` to call `create_razorpay_order`.
7. **Payment**: The user receives a Razorpay checkout link and completes payment.
8. **Fulfillment**: Razorpay fires a `payment.captured` webhook.
9. **Finalization**: The backend validates the webhook, triggers the atomic inventory decrement, attributes revenue, and marks the intent `PAYMENT_SUCCESS`.

## Conversational Product Discovery
The `Scout` agent acts as a consultative seller, narrowing down options based on specs, budget, and historical preferences before pushing to the cart.

## Cart / Quantity Semantics
- **ADD**: Increments existing quantity in the `purchase_intents` basket.
- **SET**: Overwrites existing quantity in the basket.
- Both operations are bound-checked (qty > 0) to prevent negative pricing exploits.

## Guardian Gating
The LangGraph ensures the LLM cannot bypass the `Guardian`. If `Closer` attempts to generate a payment link while the state is still `BROWSING` or `NEGOTIATING`, `Guardian` blocks it and forces the LLM to ask for user confirmation first.

## Blocked Transaction Recovery
If a transaction fails, gets stuck, or reaches an unknown state, the `reset_purchase_intent` tool allows the agent to safely clear the locked intent and generate a fresh `purchase_intent_id`, ensuring the new checkout is cleanly audited and untainted by previous failures.
