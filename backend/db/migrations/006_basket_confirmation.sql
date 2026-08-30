-- Migration 006: Basket Confirmation Snapshot

ALTER TABLE purchase_intents
ADD COLUMN confirmed_basket JSONB,
ADD COLUMN confirmed_amount_paise BIGINT,
ADD COLUMN confirmation_timestamp TIMESTAMPTZ;

-- Backfill existing confirmed intents (if any) to prevent them from breaking.
-- However, since this is a strict security invariant, it's safer to leave them null 
-- and require users to re-confirm if their intent hasn't been paid yet.
-- But for intents that are ALREADY paid, we might want to just set it to the current basket
-- so historical data looks valid.
UPDATE purchase_intents
SET confirmed_basket = basket,
    confirmed_amount_paise = amount_paise,
    confirmation_timestamp = updated_at
WHERE purchase_state IN ('ORDER_CREATING', 'PAYMENT_PENDING', 'PAYMENT_SUCCESS', 'PAYMENT_FAILED', 'PAYMENT_UNKNOWN', 'RECOVERY_PENDING', 'USER_CONFIRMED');
