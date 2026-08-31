-- Migration 004: Inventory Fulfillment & Atomic Decrement

-- 1. Add fulfillment_status to track out-of-stock payment success
ALTER TABLE purchase_intents 
ADD COLUMN IF NOT EXISTS fulfillment_status TEXT DEFAULT 'PENDING' 
CHECK (fulfillment_status IN ('PENDING', 'FULFILLED', 'UNFULFILLED', 'REFUND_PENDING', 'REFUNDED'));

ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS fulfillment_status TEXT DEFAULT 'PENDING' 
CHECK (fulfillment_status IN ('PENDING', 'FULFILLED', 'UNFULFILLED', 'REFUND_PENDING', 'REFUNDED'));

-- 2. Durable idempotency table for inventory processing
CREATE TABLE IF NOT EXISTS inventory_decrement_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE,
    purchase_intent_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Note: We map order_id instead of purchase_intent_id as the unique key to match payment capturing (order.paid / payment.captured are order-bound).

-- 3. Atomic multi-item inventory decrement RPC
CREATE OR REPLACE FUNCTION atomic_inventory_decrement(
    p_order_id TEXT,
    p_intent_id TEXT,
    p_items JSONB
) RETURNS JSONB AS $$
DECLARE
    item record;
    current_qty INT;
BEGIN
    -- Idempotency check: exactly-once execution per order
    BEGIN
        INSERT INTO inventory_decrement_events (order_id, purchase_intent_id) 
        VALUES (p_order_id, p_intent_id);
    EXCEPTION WHEN unique_violation THEN
        RETURN jsonb_build_object('status', 'already_processed', 'message', 'Inventory already decremented for this order');
    END;

    -- Validate and Lock ALL affected rows in deterministic order to avoid deadlocks
    FOR item IN 
        SELECT product_id, quantity 
        FROM jsonb_to_recordset(p_items) AS x(product_id TEXT, quantity INT)
        ORDER BY product_id
    LOOP
        -- Sanity check inputs
        IF item.quantity IS NULL OR item.quantity <= 0 THEN
            RAISE EXCEPTION 'Invalid quantity % for product %', item.quantity, item.product_id;
        END IF;

        -- Lock row
        SELECT inventory_qty INTO current_qty 
        FROM products 
        WHERE product_id = item.product_id 
        FOR UPDATE;
        
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Product % not found', item.product_id;
        END IF;
        
        -- Validate quantity
        IF current_qty < item.quantity THEN
            RAISE EXCEPTION 'Insufficient inventory for % (Requested: %, Available: %)', item.product_id, item.quantity, current_qty;
        END IF;
        
        -- Decrement atomically
        UPDATE products 
        SET inventory_qty = inventory_qty - item.quantity,
            updated_at = now()
        WHERE product_id = item.product_id;
    END LOOP;
    
    RETURN jsonb_build_object('status', 'success', 'message', 'Inventory decremented atomically');
END;
$$ LANGUAGE plpgsql;
