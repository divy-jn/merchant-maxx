# Task 28: Supabase RLS & Database Security Remediation

## 1. Original Vulnerability & Reproduction
The Supabase database allowed public access (via `SUPABASE_ANON_KEY`) because all 14 tables had `USING (true)` Row Level Security policies. This was confirmed by executing a test script (`test_rls_security.py`) that successfully ran `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on tables like `purchase_intents`, `orders`, and `audit_log` using only the public anon key.

## 2. Table-by-Table Authorization Matrix
Since the frontend exclusively uses the FastAPI backend, the database is considered a **BACKEND_ONLY** boundary. Therefore, no public access is required via PostgREST.

| Table | Policy | Role | Justification |
|-------|--------|------|---------------|
| `users` | Deny All | public, anon, authenticated | Backend-only access |
| `conversations` | Deny All | public, anon, authenticated | Backend-only access |
| `messages` | Deny All | public, anon, authenticated | Backend-only access |
| `products` | Deny All | public, anon, authenticated | Backend-only access |
| `purchase_intents` | Deny All | public, anon, authenticated | Backend-only access |
| `orders` | Deny All | public, anon, authenticated | Backend-only access |
| `payments` | Deny All | public, anon, authenticated | Backend-only access |
| `audit_log` | Deny All | public, anon, authenticated | Backend-only access |
| `webhook_events` | Deny All | public, anon, authenticated | Backend-only access |
| `inventory_decrement_events` | Deny All | public, anon, authenticated | Backend-only access |
| *All other tables...* | Deny All | public, anon, authenticated | Backend-only access |

## 3. Exact RLS Policy Changes
Migration `005_rls_hardening.sql` was applied successfully:
```sql
DROP POLICY IF EXISTS "Allow all on {table}" ON {table};
CREATE POLICY "Deny all public access on {table}" ON {table} FOR ALL TO public, anon, authenticated USING (false);
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
```

## 4. RPC Security Changes
The execution privilege for the highly sensitive idempotent inventory decrement function was revoked from public roles:
```sql
REVOKE EXECUTE ON FUNCTION atomic_inventory_decrement(TEXT, TEXT, JSONB) FROM public, anon, authenticated;
```

## 5. Security Attack Test Results (Anon Key)
The new security test (`test_rls_security.py`) was executed. The `anon` key is now fully locked out.
- `SELECT` on conversations, orders, purchase intents returns `0` rows.
- `INSERT` on orders fails (caught by pytest).
- `UPDATE` on inventory fails.
- `DELETE` on audit_log fails.
- `.rpc("atomic_inventory_decrement")` invocation fails.

## 6. Backend Service-Role Configuration
- `supabase_client.py` and `config.py` were updated to initialize the client using `SUPABASE_SERVICE_KEY`.
- A fail-fast was introduced: if `APP_ENV == "production"` and the service key is missing, the application will refuse to start, preventing silent fallback to the anon key.
- Codebase scan confirmed `SUPABASE_SERVICE_KEY` is not bundled into the React frontend. `.env` is properly ignored in `.gitignore`.

## 7. Backend Regression Test Results
**Status: BLOCKED**
The `SUPABASE_SERVICE_KEY` provided in the `.env` (`[MASKED_SERVICE_KEY_2]`) is being rejected by Supabase with the following error:
> `{"message":"Invalid API key","hint":"Double check the provided API key for typos. This API key might also be owned by another Supabase project."}`

Because the service key is invalid, the backend cannot connect to the database, causing the regression tests (`pytest backend/tests/ -v`) to fail immediately during database setup phases.

## Remaining Risks & Next Steps
1. **Provide Valid Service Key:** Please provide the correct `SUPABASE_SERVICE_KEY` for the `aynzhepktrvgtxqcdwdn` project in `.env`.
2. **Re-run Regression Tests:** Once the key is updated, I will re-run the backend regression tests to prove that the service-role operates correctly over the locked-down tables.
3. **Frontend Build Check:** I will run `npm run build` after the tests pass.
4. **Deploy:** Only after these tests pass will we generate the Cloud Run deployment command.
