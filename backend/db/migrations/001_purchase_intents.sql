ALTER TABLE orders ADD COLUMN IF NOT EXISTS purchase_intent_id TEXT;
CREATE INDEX IF NOT EXISTS idx_orders_purchase_intent ON orders(purchase_intent_id);

ALTER TABLE purchase_intents ADD COLUMN IF NOT EXISTS recommendation_id TEXT;

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    razorpay_entity_id TEXT,
    received_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_webhook_events_entity ON webhook_events(razorpay_entity_id);
ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all on webhook_events" ON webhook_events;
CREATE POLICY "Allow all on webhook_events" ON webhook_events FOR ALL USING (true);
