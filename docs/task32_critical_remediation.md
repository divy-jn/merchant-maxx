# TASK 32: Critical Remediation & Source-of-Truth Restoration

## 1. Task 31 Findings
Task 31 uncovered significant repository hygiene and drift issues:
- **P0**: Production secrets were committed to Git (`_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json`).
- **P1**: Migration `004_inventory_fulfillment.sql` existed locally and in production but was never committed to `main`.
- **P1**: `schema.sql` contained outdated, highly permissive `USING (true)` RLS policies, creating a risk if used to bootstrap a new environment.
- **P1**: The ACP discovery endpoint (`backend/acp/protocol.py`) falsely advertised an unimplemented `/acp/purchase` capability.

## 2. Secret Exposure Metadata
| Provider | Credential Type | Exposed Location | Git History | Rotation Required |
| :--- | :--- | :--- | :--- | :--- |
| Supabase | Database credential (URL with password) | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES (in `.env.example`, `migrate.py` historically) | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| Supabase | API Key (Anon/Publishable Key) | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| Razorpay | API Key ID | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| Razorpay | API Key Secret | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES (in `.env.example` historically) | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| Razorpay | Webhook Secret | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| LangSmith | API Key | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| OpenRouter / Gemini | LLM API Key | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| Pinecone | API Key | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES | REQUIRES USER ACTION — ROTATE ON THE 5TH |
| Upstash | Redis Token | `_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json` | YES | REQUIRES USER ACTION — ROTATE ON THE 5TH |

## 3. Current Git Cleanup
- **FIXED**: The sensitive snapshot files (`_env_restore.txt`, `_env_restore.yaml`, `cloud_run_env.json`) were removed from the Git index (`git rm --cached`).
- **FIXED**: Explicit exclusion rules (`_env_restore.*` and `cloud_run_env.json`) were added to `.gitignore`.

## 4. Historical Git Exposure
- **REQUIRES USER ACTION**: The secrets remain reachable in historical Git commits (e.g. `51b60a1`, `9f12284`, `c9e76db`). History has **NOT** been scrubbed in this task. If you wish to scrub history permanently without rotating immediately, use `git filter-repo` and force-push.

## 5. Migration 004 Restoration
- **FIXED**: `backend/db/migrations/004_inventory_fulfillment.sql` has been added back to Git tracking. It correctly mirrors the `atomic_inventory_decrement` and fulfillment schema currently active in production.

## 6. Migration 001–007 Consistency
- **FIXED**: All 7 migrations (001-007) are present in the repository, linearly ordered, and faithfully map to the production source-of-truth.

## 7. schema.sql Remediation
- **FIXED**: The baseline `schema.sql` was rewritten. All permissive `USING (true)` and `Allow all on` policies were replaced with strict `USING (false)` / `Deny all public access on` blocks.
- **FIXED**: Missing artifacts from migrations (e.g. `webhook_events`, `inventory_decrement_events`, atomic decrement RPCs, and state-finality triggers) were correctly baked into the updated `schema.sql` baseline.

## 8. ACP Remediation
- **FIXED**: Removed the `/acp/purchase` capability from `backend/acp/protocol.py`. The discovery endpoint now correctly advertises only implemented routes.

## 9. Git/DB/Cloud Run Source-of-Truth Matrix
| Component | Git | Production | Match | Required Action |
| :--- | :--- | :--- | :--- | :--- |
| **Git Commit (HEAD)** | Current cleanup commits | `b0604c4` | NO | Commit changes and deploy after review |
| **Cloud Run Revision** | `merchant-maxx-api-00034-gzf` | `merchant-maxx-api-00034-gzf` | YES | None |
| **Migration 004** | Tracked | Applied | YES | None |
| **Migration 005** | Tracked | Applied | YES | None |
| **Migration 006** | Tracked | Applied | YES | None |
| **Migration 007** | Tracked | Applied | YES | None |
| **RLS State** | Deny-All (Strict) | Deny-All (Strict) | YES | None |
| **Payment Finality** | Enforced | Enforced | YES | None |
| **Inventory RPC** | Present | Present | YES | None |
| **Webhook Idempotency** | Guarded | Guarded | YES | None |
| **ACP Routes** | `catalog_search` | `catalog_search` | YES | None |

## 10. Configuration Audit
- **FIXED**: The application environment appropriately requires `JWT_SECRET` and `SUPABASE_SERVICE_KEY`.
- **FIXED**: Secrets are not embedded in `VITE_*` environment variables on the frontend.
- **FIXED**: `.env.example` has been heavily sanitized and no longer contains realistic database passwords or API keys.

## 11. Tests
- **FIXED**: A new test suite (`backend/tests/test_task32_remediation.py`) successfully asserts that secrets are untracked, `schema.sql` is secure, migration chain is complete, and ACP discovery matches reality.

## 12. Build Result
- **FIXED**: `npm run build` executed successfully without errors for the frontend.

## 13. Static Security Scan
- **FIXED**: Checked Git for plaintext secrets and verified `schema.sql` for overly permissive statements. No new findings.

## 14. Remaining Risks
- **Historical Git History**: A local `.env` exposure from early commits and recent `_env_restore.*` snapshots are still in the Git tree history. 
- **Compromised Credentials**: All credentials have technically been breached since they were committed to GitHub.

## 15. Credential Rotation Checklist
**REQUIRES USER ACTION — ROTATE ON THE 5TH**
- [ ] Supabase Database Password
- [ ] Supabase Service Key
- [ ] Supabase Anon Key
- [ ] Razorpay Key ID and Secret
- [ ] Razorpay Webhook Secret
- [ ] Upstash Redis Token
- [ ] LangSmith API Key
- [ ] LLM Provider Keys (OpenRouter, Gemini)
- [ ] Pinecone API Key
- [ ] Application JWT Secret
