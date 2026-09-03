> **Project status — Under Development**
>
> Merchant Maxx is under active development. The core application source is maintained in `backend/` and `frontend/`, with supporting documentation in `docs/`.
>
> **Current state:**
> - The production application is deployed through the existing backend/frontend deployment setup.
> - The restored development history contains **108 commits** with original author/committer metadata and timestamps preserved through the security rewrite.
> - Previously exposed credentials were scrubbed from reachable Git history; real credentials must remain in environment/secret-manager configuration and must not be committed.
> - The latest local backend validation recorded **156 passing tests and 1 xpassed**. The GitHub Actions backend test check still needs to be resolved before calling CI fully green.
> - Development-only artifacts have been moved into `underConstruction/` so the repository root stays focused on the application and required project files.
>
> This status block is intentionally kept current as the project continues through development, testing, hardening, and deployment work.
>
> ---
>
# 🐛 Bug Tracker — Merchant Maxx

> All known bugs, reproduction steps, and resolution status.

---

## Template

```
### BUG-XXX: [Title]
- **Status:** 🔴 Open | 🟡 In Progress | 🟢 Fixed
- **Severity:** Critical | High | Medium | Low
- **Found:** YYYY-MM-DD
- **Component:** Backend / Frontend / Agent / Razorpay / DB
- **Steps to reproduce:**
  1. ...
- **Expected:** ...
- **Actual:** ...
- **Fix:** ...
```

---

### BUG-B20: Duplicate Supabase client in Ledger
- **Status:** 🟢 Fixed
- **Severity:** Medium
- **Found:** 2026-08-25
- **Component:** Backend
- **Steps to reproduce:** Start server. `ledger.py` initializes its own Supabase client separate from `auth.py`.
- **Fix:** Extracted to `utils/supabase_client.py`.

### BUG-B21: Missing `langchain-google-genai` in requirements
- **Status:** 🟢 Fixed
- **Severity:** High
- **Found:** 2026-08-25
- **Component:** Backend
- **Steps to reproduce:** Clone repo, `pip install -r requirements.txt`. Fails to run Scout agent.
- **Fix:** Added `langchain-google-genai` to `requirements.txt`.

### BUG-B22: CORS_ORIGINS doesn't support multiple URLs
- **Status:** 🟢 Fixed
- **Severity:** Medium
- **Found:** 2026-08-25
- **Component:** Backend
- **Steps to reproduce:** Set `CORS_ORIGINS=url1,url2` in `.env`.
- **Fix:** Split on comma in `main.py` and pass as list to CORS middleware.

### BUG-B23: Missing `requests` in requirements
- **Status:** 🟢 Fixed
- **Severity:** Low
- **Found:** 2026-08-25
- **Component:** Backend
- **Fix:** Added to `requirements.txt`.

### BUG-B24: Missing `__init__.py` files
- **Status:** 🟢 Fixed
- **Severity:** Low
- **Found:** 2026-08-25
- **Component:** Backend
- **Steps to reproduce:** Build Docker image. Python namespace packages might fail imports.
- **Fix:** Added `__init__.py` to `routes/`, `agents/`, `search/`, `cache/`, `evals/`.

### BUG-B25: Guardian `user_confirmed` False Negatives
- **Status:** 🟢 Fixed
- **Severity:** High
- **Found:** 2026-08-25
- **Component:** Agent
- **Steps to reproduce:** User says "yes confirm", LLM generates tool call but forgets `user_confirmed=True`.
- **Fix:** Added deterministic override logic in `closer_node` inside `closer.py`.

---

### BUG-B26: Deprecated Embedding Model Crashes Chat
- **Status:** 🟢 Fixed
- **Severity:** Critical
- **Found:** 2026-08-27
- **Component:** Backend (`search/vector_store.py`)
- **Steps to reproduce:** Send any chat message. Scout calls `search_catalog` → vector search uses `embedding-001` → 404 NOT_FOUND.
- **Expected:** Chat returns AI response.
- **Actual:** 500 Internal Server Error.
- **Fix:** Changed model to `models/gemini-embedding-001`. Added keyword search fallback in `tools.py`.

### BUG-B27: Frontend-Backend Chat Contract Mismatch
- **Status:** dYY Fixed
- **Severity:** High
- **Found:** 2026-08-27
- **Component:** Frontend (`AgentChat.jsx`) ↔ Backend (`routes/chat.py`)
- **Steps to reproduce:** Send a chat message, then reload the page.
- **Expected:** Chat history persists across page reloads.
- **Actual:** History is lost. Frontend sends `session_id` but backend expects `conversation_id`. New conversation created on every message.
- **Fix:** Rename frontend params to `conversation_id` and track the returned `conversation_id` from POST response.

### BUG-B28: Cloud Run Cold Start Timeout
- **Status:** 🟡 Known Issue
- **Severity:** High
- **Found:** 2026-08-27
- **Component:** Infrastructure (GCP Cloud Run)
- **Steps to reproduce:** Wait 15+ minutes, then visit `merchant-maxx.vercel.app`.
- **Expected:** Page loads within 3 seconds.
- **Actual:** "Failed to fetch catalog" error — backend takes 30+ seconds to cold-start.
- **Fix:** Set `--min-instances=1` or add frontend retry/loading spinner.

### BUG-B29: CORS OPTIONS Returns 400
- **Status:** dYY Fixed
- **Severity:** Medium
- **Found:** 2026-08-27
- **Component:** Backend (`main.py` middleware)
- **Steps to reproduce:** Send `OPTIONS /catalog/` preflight request.
- **Expected:** 200 with CORS headers.
- **Actual:** 400 Bad Request.
- **Fix:** Verify middleware ordering — CORS should be outermost.

### BUG-B30: Pinecone Index Dimension Mismatch
- **Status:** 🟢 Fixed
- **Severity:** Critical
- **Found:** 2026-08-27
- **Component:** Backend (`search/vector_store.py`)
- **Steps to reproduce:** Start server after changing embedding model. Old index has 768 dims, new model outputs 3072.
- **Fix:** Added auto-detection: deletes and recreates index on dimension mismatch.

### BUG-B31: Empty Files (Login.jsx, AgentTrace.jsx, AuthContext.jsx)
- **Status:** dYY Fixed
- **Severity:** Medium
- **Found:** 2026-08-27
- **Component:** Frontend
- **Steps to reproduce:** Check file sizes — all 0 bytes.
- **Fix:** Regenerate from git history or rewrite.

### BUG-B32: `fix_urls.py` Left in Repo Root
- **Status:** dYY Fixed
- **Severity:** Low
- **Found:** 2026-08-27
- **Component:** Repository hygiene
- **Fix:** Delete the file or add to `.gitignore`.

### BUG-B33: Cloud Run Still Uses Old Embedding Model
- **Status:** dYY Fixed
- **Severity:** Critical
- **Found:** 2026-08-27
- **Component:** Infrastructure
- **Steps to reproduce:** Call `POST /chat/` on the live Cloud Run URL.
- **Fix:** Commit fixes, push to `main`, redeploy to Cloud Run.

---

### BUG-B34: CONTEXT.md is Stale
- **Status:** 🟡 Open
- **Severity:** Medium
- **Found:** 2026-08-27
- **Component:** `CONTEXT.md`
- **Description:** "Current Status" section still says "PLANNING COMPLETE → READY TO BUILD". Doesn't reflect Days 1-7 of development.
- **Fix:** Update the Current Status section with actual project state.

### BUG-B35: Frontend Doesn't Send JWT Auth Token
- **Status:** dYY Fixed
- **Severity:** High
- **Found:** 2026-08-27
- **Component:** Frontend (all pages)
- **Description:** All `fetch()` calls omit `Authorization: Bearer` header. Auth middleware returns `None` (guest mode). Chat conversations aren't linked to users. `/chat/conversations` always empty.
- **Root cause:** `AuthContext.jsx` is 0 bytes.
- **Fix:** Write AuthContext, wrap app in auth provider, add Bearer headers to all API calls.

### BUG-B36: Booster & Campaigner Agents Not Wired Into MAXX Graph
- **Status:** 🟡 Open
- **Severity:** Medium
- **Found:** 2026-08-27
- **Component:** Backend (`agents/maxx.py`)
- **Description:** `booster.py` and `campaigner.py` exist but are never added as nodes in the LangGraph StateGraph. They are dead code.
- **Fix:** Add them to the graph or acknowledge as out-of-scope for hackathon.

### BUG-B37: Dev Notes Say Port 8000, Actual is 8002
- **Status:** 🟡 Open
- **Severity:** Low
- **Found:** 2026-08-27
- **Component:** `docs/dev-notes.md`
- **Fix:** Update port reference from 8000 to 8002.

### BUG-B38: `.env.example` Contains Real-Looking API Keys
- **Status:** 🟡 Open
- **Severity:** Medium
- **Found:** 2026-08-27
- **Component:** `.env.example`
- **Description:** Contains Razorpay test keys, Supabase keys that look real instead of placeholders.
- **Fix:** Verify if keys are real, rotate if needed, replace with placeholder values.

### BUG-B39: No SPA Fallback on Vercel
- **Status:** dYY Fixed
- **Severity:** Low
- **Found:** 2026-08-27
- **Component:** Frontend (Vercel deployment)
- **Description:** Direct navigation to `/chat` or `/audit` may 404 without `vercel.json` rewrites.
- **Fix:** Add `vercel.json` with `{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }`.

---

*Last updated: 2026-08-27*
