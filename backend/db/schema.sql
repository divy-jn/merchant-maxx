-- Users table (for persistent auth)
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'merchant')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('APPROVED', 'REJECTED', 'PENDING')),
    input_summary TEXT DEFAULT '', output_summary TEXT DEFAULT '', reasoning TEXT DEFAULT '',
    risk_score REAL DEFAULT 0.0, constitutional_check JSONB DEFAULT '{}'::jsonb,
    razorpay_entity_id TEXT, timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all on users" ON users;
DROP POLICY IF EXISTS "Allow all on conversations" ON conversations;
DROP POLICY IF EXISTS "Allow all on messages" ON messages;
DROP POLICY IF EXISTS "Allow all on audit_log" ON audit_log;
CREATE POLICY "Allow all on users" ON users FOR ALL USING (true);
CREATE POLICY "Allow all on conversations" ON conversations FOR ALL USING (true);
CREATE POLICY "Allow all on messages" ON messages FOR ALL USING (true);
CREATE POLICY "Allow all on audit_log" ON audit_log FOR ALL USING (true);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY, merchant_id TEXT DEFAULT 'merchant_mxx_001', name TEXT,
    description TEXT, category TEXT, subcategory TEXT, brand TEXT, price_paise BIGINT,
    currency TEXT DEFAULT 'INR', inventory_qty INT, active BOOLEAN DEFAULT true, rating REAL,
    tags JSONB DEFAULT '[]'::jsonb, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY, merchant_id TEXT DEFAULT 'merchant_mxx_001', name TEXT,
    email TEXT, phone TEXT, city TEXT, state TEXT, segment TEXT, first_order_at TEXT,
    last_order_at TEXT, total_orders INT, total_spent_paise BIGINT, created_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY, merchant_id TEXT DEFAULT 'merchant_mxx_001', customer_id TEXT,
    status TEXT, subtotal_paise BIGINT, discount_paise BIGINT, tax_paise BIGINT,
    total_paise BIGINT, currency TEXT DEFAULT 'INR', source TEXT, purchase_state TEXT,
    created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id TEXT PRIMARY KEY, order_id TEXT, product_id TEXT, quantity INT,
    unit_price_paise BIGINT, discount_paise BIGINT, total_paise BIGINT
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY, order_id TEXT, customer_id TEXT, amount_paise BIGINT,
    currency TEXT DEFAULT 'INR', status TEXT, method TEXT, failure_code TEXT,
    failure_reason TEXT, razorpay_payment_id TEXT, initiated_at TIMESTAMPTZ, completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY, payment_id TEXT, order_id TEXT, customer_id TEXT,
    amount_paise BIGINT, status TEXT, reason TEXT, razorpay_refund_id TEXT,
    created_at TIMESTAMPTZ, processed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS customer_events (
    event_id TEXT PRIMARY KEY, customer_id TEXT, merchant_id TEXT DEFAULT 'merchant_mxx_001',
    product_id TEXT, session_id TEXT, event_type TEXT, quantity INT, event_value_paise BIGINT,
    created_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS product_affinity (
    product_id TEXT, related_product_id TEXT, support_score REAL, confidence_score REAL,
    lift_score REAL, co_purchase_count INT, PRIMARY KEY (product_id, related_product_id)
);
CREATE TABLE IF NOT EXISTS customer_metrics (
    customer_id TEXT PRIMARY KEY, recency_days INT, order_frequency REAL,
    lifetime_value_paise BIGINT, avg_order_value_paise BIGINT, purchase_probability REAL,
    churn_probability REAL, preferred_category TEXT, segment TEXT, calculated_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY, merchant_id TEXT DEFAULT 'merchant_mxx_001', name TEXT,
    campaign_type TEXT, target_segment TEXT, target_category TEXT, discount_type TEXT,
    discount_value REAL, budget_paise BIGINT, start_at TIMESTAMPTZ, end_at TIMESTAMPTZ,
    status TEXT, impressions INT, conversions INT, revenue_generated_paise BIGINT
);
CREATE TABLE IF NOT EXISTS recommendation_events (
    recommendation_id TEXT PRIMARY KEY, session_id TEXT, customer_id TEXT,
    merchant_id TEXT DEFAULT 'merchant_mxx_001', source_product_id TEXT,
    recommended_product_id TEXT, recommendation_type TEXT, agent_name TEXT, score REAL,
    reason TEXT, shown_at TIMESTAMPTZ, clicked_at TIMESTAMPTZ, accepted_at TIMESTAMPTZ,
    resulting_order_id TEXT, revenue_paise BIGINT, status TEXT
);
CREATE TABLE IF NOT EXISTS agent_audit (
    audit_id TEXT PRIMARY KEY, session_id TEXT, customer_id TEXT,
    merchant_id TEXT DEFAULT 'merchant_mxx_001', agent_name TEXT, action_type TEXT,
    entity_type TEXT, entity_id TEXT, amount_paise BIGINT DEFAULT 0, status TEXT,
    user_confirmed BOOLEAN DEFAULT false, guardian_approved BOOLEAN DEFAULT false,
    risk_score REAL DEFAULT 0.0, reasoning TEXT, input_summary TEXT, output_summary TEXT,
    failure_code TEXT, failure_reason TEXT, razorpay_entity_id TEXT, purchase_state TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS entity_mapping (
    mapping_id UUID DEFAULT gen_random_uuid() PRIMARY KEY, merchant_id TEXT DEFAULT 'merchant_mxx_001',
    synthetic_id TEXT NOT NULL, entity_type TEXT NOT NULL, razorpay_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Authoritative durable purchase state. LangGraph checkpoints are conversational only.
CREATE TABLE IF NOT EXISTS purchase_intents (
    purchase_intent_id TEXT PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    customer_id TEXT REFERENCES customers(customer_id) ON DELETE SET NULL,
    merchant_id TEXT DEFAULT 'merchant_mxx_001',
    purchase_state TEXT NOT NULL DEFAULT 'PURCHASE_PENDING',
    basket JSONB NOT NULL DEFAULT '[]'::jsonb,
    subtotal_paise BIGINT NOT NULL DEFAULT 0,
    discount_paise BIGINT NOT NULL DEFAULT 0,
    tax_paise BIGINT NOT NULL DEFAULT 0,
    amount_paise BIGINT NOT NULL DEFAULT 0,
    user_confirmed BOOLEAN NOT NULL DEFAULT false,
    razorpay_order_id TEXT,
    razorpay_payment_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_purchase_intents_customer ON purchase_intents(customer_id);
CREATE INDEX IF NOT EXISTS idx_purchase_intents_conversation ON purchase_intents(conversation_id);
CREATE INDEX IF NOT EXISTS idx_purchase_intents_state ON purchase_intents(purchase_state);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_mapping_razorpay ON entity_mapping(merchant_id, entity_type, razorpay_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_mapping_synthetic ON entity_mapping(merchant_id, entity_type, synthetic_id);

DO $$ BEGIN ALTER TABLE orders ADD CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE order_items ADD CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE order_items ADD CONSTRAINT fk_oi_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE payments ADD CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE payments ADD CONSTRAINT fk_payments_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE refunds ADD CONSTRAINT fk_refunds_payment FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE refunds ADD CONSTRAINT fk_refunds_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE customer_events ADD CONSTRAINT fk_ce_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE customer_events ADD CONSTRAINT fk_ce_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE recommendation_events ADD CONSTRAINT fk_reco_source_product FOREIGN KEY (source_product_id) REFERENCES products(product_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE recommendation_events ADD CONSTRAINT fk_reco_recommended_product FOREIGN KEY (recommended_product_id) REFERENCES products(product_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE recommendation_events ADD CONSTRAINT fk_reco_order FOREIGN KEY (resulting_order_id) REFERENCES orders(order_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_customer_events_customer ON customer_events(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_events_session ON customer_events(session_id);
CREATE INDEX IF NOT EXISTS idx_product_affinity_product ON product_affinity(product_id);
CREATE INDEX IF NOT EXISTS idx_customer_metrics_segment ON customer_metrics(segment);
CREATE INDEX IF NOT EXISTS idx_recommendation_events_session ON recommendation_events(session_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_events_status ON recommendation_events(status);
CREATE INDEX IF NOT EXISTS idx_agent_audit_session ON agent_audit(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_audit_agent ON agent_audit(agent_name);
CREATE INDEX IF NOT EXISTS idx_entity_mapping_synthetic ON entity_mapping(synthetic_id);
CREATE INDEX IF NOT EXISTS idx_entity_mapping_razorpay ON entity_mapping(razorpay_id);

ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_affinity ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_mapping ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_intents ENABLE ROW LEVEL SECURITY;

DO $$ DECLARE tbl TEXT; BEGIN FOR tbl IN SELECT unnest(ARRAY['products','customers','orders','order_items','payments','refunds','customer_events','product_affinity','customer_metrics','campaigns','recommendation_events','agent_audit','entity_mapping','purchase_intents']) LOOP EXECUTE format('DROP POLICY IF EXISTS "Allow all on %I" ON %I', tbl, tbl); EXECUTE format('CREATE POLICY "Allow all on %I" ON %I FOR ALL USING (true)', tbl, tbl); END LOOP; END $$;
