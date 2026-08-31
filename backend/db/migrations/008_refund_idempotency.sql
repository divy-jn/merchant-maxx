-- Migration 008: Refund Idempotency & Architecture

-- Step 1: Ensure refunds table exists (it should exist from schema.sql, but we'll alter it)
CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY, 
    payment_id TEXT, 
    order_id TEXT, 
    customer_id TEXT,
    amount_paise BIGINT, 
    status TEXT, 
    reason TEXT, 
    razorpay_refund_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(), 
    processed_at TIMESTAMPTZ
);

-- Step 2: Add idempotency and safety columns
ALTER TABLE refunds ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE refunds ADD COLUMN IF NOT EXISTS error_reason TEXT;
ALTER TABLE refunds ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Step 3: Add explicit constraints to prevent duplicate refunds for the same context
-- This ensures that only ONE active or successful refund can exist per payment/idempotency context.
CREATE UNIQUE INDEX IF NOT EXISTS uq_refund_idempotency ON refunds(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_refund_payment_success ON refunds(payment_id) WHERE status IN ('REFUND_PENDING', 'REFUND_REQUESTED', 'REFUNDED', 'REFUND_UNKNOWN');

-- Step 4: Add foreign keys if they don't exist
DO $$ 
BEGIN 
    ALTER TABLE refunds ADD CONSTRAINT fk_refunds_payment FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL; 
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ 
BEGIN 
    ALTER TABLE refunds ADD CONSTRAINT fk_refunds_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE SET NULL; 
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Step 5: Enable RLS and deny all
ALTER TABLE refunds ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all on refunds" ON refunds;
DROP POLICY IF EXISTS "Deny all public access on refunds" ON refunds;
CREATE POLICY "Deny all public access on refunds" ON refunds FOR ALL TO public, anon, authenticated USING (false);

-- Trigger to prevent downgrade of terminal REFUNDED status
CREATE OR REPLACE FUNCTION trg_prevent_refund_downgrade()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'REFUNDED' THEN
        IF NEW.status != 'REFUNDED' THEN
            RAISE EXCEPTION 'CRITICAL: Cannot downgrade refund status from REFUNDED to %', NEW.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_refund_finality ON refunds;
CREATE TRIGGER enforce_refund_finality
BEFORE UPDATE ON refunds
FOR EACH ROW
EXECUTE FUNCTION trg_prevent_refund_downgrade();
