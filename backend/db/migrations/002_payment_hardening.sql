-- Migration 002: Payment lifecycle hardening
-- Safe to re-run (all operations are IF NOT EXISTS / IF EXISTS)

-- 1. Prevent duplicate orders for the same purchase intent (TOCTOU race fix)
--    NOTE: partial index — only constrains rows where purchase_intent_id is set
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_purchase_intent
    ON orders(purchase_intent_id) WHERE purchase_intent_id IS NOT NULL;

-- 2. Prevent duplicate Razorpay order IDs on purchase intents
CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_intents_rzp_order
    ON purchase_intents(razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;

-- 3. Additional webhook tracking columns
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS razorpay_payment_id TEXT;

-- 4. Payment update timestamp on purchase_intents
ALTER TABLE purchase_intents ADD COLUMN IF NOT EXISTS payment_updated_at TIMESTAMPTZ;
