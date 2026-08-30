-- Migration 007: Payment State Finality
-- This migration adds BEFORE UPDATE triggers to strictly prevent
-- downgrading a terminal payment state (PAYMENT_SUCCESS for purchase_intents,
-- CAPTURED for orders) back to a non-terminal or failed state.

-- 1. purchase_intents trigger
CREATE OR REPLACE FUNCTION trg_prevent_intent_downgrade()
RETURNS TRIGGER AS $$
BEGIN
    -- If the row was already in PAYMENT_SUCCESS...
    IF OLD.purchase_state = 'PAYMENT_SUCCESS' THEN
        -- ...and the UPDATE attempts to change it to something else...
        IF NEW.purchase_state != 'PAYMENT_SUCCESS' THEN
            RAISE EXCEPTION 'CRITICAL: Cannot downgrade purchase_intent from PAYMENT_SUCCESS to %', NEW.purchase_state;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_intent_finality ON purchase_intents;
CREATE TRIGGER enforce_intent_finality
BEFORE UPDATE ON purchase_intents
FOR EACH ROW
EXECUTE FUNCTION trg_prevent_intent_downgrade();


-- 2. orders trigger
CREATE OR REPLACE FUNCTION trg_prevent_order_downgrade()
RETURNS TRIGGER AS $$
BEGIN
    -- If the row was already CAPTURED...
    IF OLD.status = 'CAPTURED' THEN
        -- ...and the UPDATE attempts to change it to something else...
        IF NEW.status != 'CAPTURED' THEN
            RAISE EXCEPTION 'CRITICAL: Cannot downgrade order status from CAPTURED to %', NEW.status;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_order_finality ON orders;
CREATE TRIGGER enforce_order_finality
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION trg_prevent_order_downgrade();
