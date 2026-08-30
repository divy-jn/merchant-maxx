-- Migration 003: Recommendation idempotency hardening
-- Safe to re-run (all operations are IF NOT EXISTS)
-- NO destructive operations (no DROP, no data loss)

-- 1. Ensure recommendation_events.recommendation_id has a unique constraint
--    The application uses upsert with recommendation_id as the identity key,
--    but without a DB-level unique constraint the upsert may silently insert
--    duplicates under concurrent execution.
--
--    NOTE: If duplicate recommendation_id rows already exist, this will fail.
--    Run the de-duplication query below BEFORE applying this index:
--
--    DELETE FROM recommendation_events a
--    USING recommendation_events b
--    WHERE a.ctid < b.ctid
--      AND a.recommendation_id = b.recommendation_id;
--
CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendation_events_rec_id
    ON recommendation_events(recommendation_id);
