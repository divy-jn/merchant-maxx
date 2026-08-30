-- Migration 005: RLS Hardening and Direct Database Security Remediation
-- This migration removes public/anon access from all tables because the frontend 
-- connects exclusively through the FastAPI backend. The backend uses the Service Role key.

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'users',
        'conversations',
        'messages',
        'audit_log',
        'products',
        'customers',
        'orders',
        'order_items',
        'payments',
        'refunds',
        'customer_events',
        'product_affinity',
        'customer_metrics',
        'campaigns',
        'recommendation_events',
        'agent_audit',
        'entity_mapping',
        'purchase_intents',
        'inventory_decrement_events',
        'webhook_events'
    ]) LOOP
        -- 1. Drop existing permissive policies
        EXECUTE format('DROP POLICY IF EXISTS "Allow all on %I" ON %I', tbl, tbl);
        
        -- 2. Create Deny-All policies for public roles (anon, authenticated)
        EXECUTE format('DROP POLICY IF EXISTS "Deny all public access on %I" ON %I', tbl, tbl);
        EXECUTE format('CREATE POLICY "Deny all public access on %I" ON %I FOR ALL TO public, anon, authenticated USING (false)', tbl, tbl);
        
        -- Ensure RLS is actually enabled
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
    END LOOP;
END
$$;

-- Revoke RPC execution privileges from public roles for the atomic inventory decrement
REVOKE EXECUTE ON FUNCTION atomic_inventory_decrement(TEXT, TEXT, JSONB) FROM public, anon, authenticated;
