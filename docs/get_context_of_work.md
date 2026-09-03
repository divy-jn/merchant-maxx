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
# 🧠 Get Context of Work — Merchant Maxx

> **Purpose:** Complete context snapshot of all work done, current state, and all bugs/breaks in the project.  
> **Generated:** 2026-08-27  
> **For:** Any human or AI continuing this project.

---

## 1. Project Overview

**Merchant Maxx** is a multi-agent AI commerce platform built for the **Razorpay AI Hackathon (Track 01: AI Growth & Agentic Commerce)**. It features:

- 7 AI agents (MAXX, Scout, Closer, Booster, Campaigner, Guardian, Ledger) orchestrated via LangGraph
- Conversational checkout via an AI assistant (MAXX)
- ACP-inspired agent-commerce protocol with `.well-known` discovery
- Razorpay test-mode integration (Items, Orders, Payments, Payment Links, Refunds)
- Constitutional AI safety gate (Guardian) that validates every money action
- Full audit trail (Ledger) with risk scoring and explainable reasoning
- Premium dark-mode glassmorphism frontend

**Owner:** Divy Jain (`divy-jn`) | **Repo:** [github.com/divy-jn/merchant-maxx](https://github.com/divy-jn/merchant-maxx)

---

## 2. What Has Been Built (Days 0–7)

### Day 0 — Planning & Research ✅
- Defined project scope, researched Razorpay APIs, ACP/A2A/MCP protocol stack
- Studied Razorpay AI Playbook (B.5 multi-agent orchestration, G.22-G.28 fintech guardrails)
- Created full docs structure: `plan.md`, `tasks.md`, `decisions.md`, `qna.md`, `bugs.md`, `progress.md`, `deployment.md`, `dev-notes.md`, `chat-history.md`
- Created `CONTEXT.md` as the universal entry point for any AI/human

### Day 1 — Setup & Foundation ✅
- Scaffolded FastAPI backend + Vite React frontend
- Created Supabase project (ID: `merchantmaxx`) with schema migration
- Installed all Python and JS dependencies
- Created `.env` and `.env.example`
- Created GitHub repo and pushed initial commit

### Day 2 — Razorpay Client + Catalog ✅
- Built Razorpay SDK wrappers: `client.py`, `items.py`, `customers.py`, `orders.py`, `payments.py`, `payment_links.py`, `refunds.py`
- Created `routes/catalog.py` REST endpoints
- Seeded 10 demo electronics products to Razorpay test account

### Day 3 — ACP Protocol + Core Agents ✅
- Built ACP layer: `acp/schemas.py`, `acp/protocol.py`, `acp/discovery.py`
- Built Scout Agent (product discovery + intent)
- Built Closer Agent (checkout + payment link generation)
- Built MAXX Orchestrator via LangGraph StateGraph
- Built agent tools with JSON schemas in `agents/tools.py`

### Day 4 — Guardian + Audit + Upsell/Campaign ✅
- Built Guardian Agent (deterministic + AI-based safety gate)
- Built Constitutional AI rules engine (`audit/constitutional.py`, `audit/evaluator.py`)
- Built Ledger Agent for immutable audit logging to Supabase
- Built Booster Agent (cross-sell) and Campaigner Agent (discounts)
- Created `routes/audit.py` REST endpoints

### Day 5 — Frontend: Dashboard + Chat + Catalog ✅
- Implemented premium dark-mode glassmorphism theme (`index.css`)
- Created `DashboardLayout` with sidebar navigation
- Created `Catalog` page (product grid from backend)
- Created `AgentChat` page (conversational checkout with MAXX)
- Created `AuditTrail` page (immutable ledger logs table)

### Day 6 — Architecture Refactor + Production Readiness 🟡
- Refactored MAXX to be the only customer-facing agent
- Added JWT-based auth system (`routes/auth.py`, `middleware/auth_middleware.py`)
- Added persistent chat history in Supabase (conversations + messages tables)
- Added LangSmith tracing integration (`routes/traces.py`)
- Added Pinecone vector search (`search/vector_store.py`)
- Added Upstash Redis caching (`cache/redis_client.py`)
- Added Rate Limiting middleware (`middleware/rate_limit.py`)
- Added Global Error Handler middleware (`middleware/error_handler.py`)
- Fixed pre-existing bugs B20-B25

### Day 7 — Deployment + Testing 🟡
- **Backend:** Deployed to Google Cloud Run (`merchant-maxx-api-1066165000716.us-central1.run.app`)
- **Frontend:** Deployed to Vercel (`merchant-maxx.vercel.app`)
- Created comprehensive E2E test script (`backend/scripts/e2e_test.py`)
- Ran full API test suite — discovered critical embedding model deprecation and several integration bugs
- **NOT completed:** README, demo video, agent simulator page, campaigns page

---

## 3. Architecture Summary

```
User → Vercel CDN (React Frontend)
           ↓ API calls
       GCP Cloud Run (FastAPI Backend)
           ├── MAXX Orchestrator (LangGraph)
           │   ├── Scout (discovery tools: search_catalog, get_product_details)
           │   ├── Closer (payment tools: create_payment_link_for_product)
           │   ├── Booster (upsell - not wired into graph)
           │   ├── Campaigner (campaigns - not wired into graph)
           │   └── Guardian (safety gate, validates all money actions)
           ├── Ledger (audit logging to Supabase)
           ├── ACP Protocol (/.well-known/agent-commerce.json)
           ├── Razorpay SDK Wrapper (test mode)
           ├── Pinecone (vector search)
           └── Upstash Redis (caching)
                ↓
           Supabase PostgreSQL (users, conversations, messages, audit_log)
```

### Key Middleware Stack (order matters in `main.py`):
1. `GlobalErrorMiddleware` — catches unhandled exceptions
2. `RateLimitMiddleware` — 100 req/min per IP via Redis
3. `CORSMiddleware` — cross-origin support

### API Routes:
| Prefix | Router | Purpose |
|--------|--------|---------|
| `/` | `main.py` | Health check |
| `/auth/` | `routes/auth.py` | Register, Login, Me |
| `/catalog/` | `routes/catalog.py` | List/Get items from Razorpay |
| `/chat/` | `routes/chat.py` | Chat with MAXX, history, conversations |
| `/audit/` | `routes/audit.py` | View audit logs |
| `/traces/` | `routes/traces.py` | LangSmith traces |
| `/.well-known/` | `acp/protocol.py` | ACP discovery |
| `/acp/` | `acp/discovery.py` | ACP catalog search |

---

## 4. Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 001 | ACP-inspired REST (not full A2A) | Commerce-focused, buildable in 1 week |
| 002 | LiteLLM as library (not proxy) | Zero infrastructure, inline import |
| 003 | GCP Cloud Run for backend | $300 free credits, auto-scale, 1-command deploy |
| 004 | Split deployment (Vercel + Cloud Run) | CDN frontend = zero backend load for page loads |
| 005 | `razorpay-python` SDK (not raw HTTP) | Official, handles auth/retries/errors |
| 007 | MAXX-only customer-facing agent | Internal agents invisible to users |
| 008 | In-memory → JWT auth | Started simple, upgraded to persistent JWT |
| 009 | In-memory → Supabase chat history | Started simple, upgraded to DB persistence |

---

## 5. Environment Configuration

### Services Used:
| Service | Status | Notes |
|---------|--------|-------|
| **Razorpay** | ✅ Working | Test mode (`rzp_test_` keys) |
| **Supabase** | ✅ Working | PostgreSQL + Auth tables |
| **Gemini** | ✅ Working | `gemini-3.6-flash` for LLM, `gemini-embedding-001` for embeddings |
| **Pinecone** | ⚠️ Needs index rebuild | Index dimension mismatch (768 vs 3072) |
| **Upstash Redis** | ✅ Working | Rate limiting + caching |
| **LangSmith** | ✅ Working | Tracing configured |
| **Vercel** | ✅ Deployed | `merchant-maxx.vercel.app` |
| **Cloud Run** | ⚠️ Cold start issues | `merchant-maxx-api-*.run.app` |

### Frontend Env Vars (Vercel):
- `VITE_API_URL` → Cloud Run backend URL

### Backend Env Vars:
- `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`
- `PINECONE_API_KEY`
- `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
- `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- `CORS_ORIGINS`, `JWT_SECRET`

---

## 6. What's Incomplete

| Feature | Status | What's Missing |
|---------|--------|---------------|
| **Agent Simulator** page | ❌ Not built | `AgentSimulator.jsx` never created |
| **Campaigns** page | ❌ Not built | `Campaigns.jsx` never created |
| **Login** page | ❌ Empty file | `Login.jsx` is 0 bytes |
| **Agent Trace** viewer | ❌ Empty file | `AgentTrace.jsx` is 0 bytes |
| **Auth Context** | ❌ Empty file | `AuthContext.jsx` is 0 bytes |
| **Booster Agent** in graph | ❌ Not wired | `booster.py` exists but not in MAXX StateGraph |
| **Campaigner Agent** in graph | ❌ Not wired | `campaigner.py` exists but not in MAXX StateGraph |
| **README.md** | ❌ Stub only | `docs/README.md` is a stub, no proper root README |
| **Demo Video** | ❌ Not recorded | Required for hackathon submission |
| **End-to-end tests** | ⚠️ Partial | Test script exists but chat tests fail due to bugs |
| **Responsive layout** | ⚠️ Not verified | No mobile testing done |
| **SSE streaming** | ❌ Not implemented | Chat uses request/response, not token-by-token streaming |
| **Razorpay Checkout.js** | ❌ Not integrated | Frontend has no Razorpay checkout modal |
| **CONTEXT.md** status | ⚠️ Stale | Still says "PLANNING COMPLETE → READY TO BUILD" |

---

## 7. File Tree (Key Source Files Only)

```
merchant-maxx/
├── CONTEXT.md                          # Project entry point (STALE)
├── .env                                # Secrets (not committed)
├── .env.example                        # Template with placeholder keys
├── fix_urls.py                         # ⚠️ One-off script, should be deleted
├── docs/
│   ├── plan.md                         # 7-day execution plan
│   ├── tasks.md                        # Task tracker
│   ├── progress.md                     # Daily progress journal
│   ├── decisions.md                    # Architecture decisions
│   ├── bugs.md                         # Bug tracker (B20-B33)
│   ├── chat-history.md                 # Session logs
│   ├── deployment.md                   # Deployment guide
│   ├── dev-notes.md                    # Command reference
│   └── qna.md                          # Planning Q&A
├── backend/
│   ├── main.py                         # FastAPI entry point
│   ├── config.py                       # Pydantic Settings
│   ├── Dockerfile                      # Cloud Run container
│   ├── requirements.txt                # Python deps
│   ├── agents/
│   │   ├── maxx.py                     # LangGraph orchestrator (Scout↔Closer)
│   │   ├── scout.py                    # Discovery agent
│   │   ├── closer.py                   # Purchase agent
│   │   ├── guardian.py                 # Safety gate
│   │   ├── ledger.py                   # Audit logger
│   │   ├── booster.py                  # Upsell (NOT in graph)
│   │   ├── campaigner.py              # Campaigns (NOT in graph)
│   │   └── tools.py                    # search_catalog, get_product_details, create_payment_link
│   ├── routes/
│   │   ├── catalog.py                  # GET /catalog/
│   │   ├── chat.py                     # POST /chat/, GET /chat/history
│   │   ├── audit.py                    # GET /audit/
│   │   ├── auth.py                     # POST /auth/register, /auth/login
│   │   └── traces.py                   # GET /traces/latest
│   ├── acp/
│   │   ├── protocol.py                 # /.well-known/agent-commerce.json
│   │   ├── discovery.py                # POST /acp/catalog/search
│   │   └── schemas.py                  # ACP Pydantic models
│   ├── search/vector_store.py          # Pinecone + Gemini embeddings
│   ├── cache/redis_client.py           # Upstash Redis
│   ├── audit/constitutional.py         # Safety rules engine
│   ├── middleware/
│   │   ├── auth_middleware.py          # JWT extraction
│   │   ├── rate_limit.py              # Redis rate limiter
│   │   └── error_handler.py           # Global error catch
│   └── razorpay_service/              # SDK wrappers
├── frontend/
│   ├── src/
│   │   ├── App.jsx                     # Router (3 routes: /, /chat, /audit)
│   │   ├── index.css                   # Design system
│   │   ├── layouts/DashboardLayout.jsx # Sidebar + Outlet
│   │   ├── pages/
│   │   │   ├── Catalog.jsx             # Product grid
│   │   │   ├── AgentChat.jsx           # Chat with MAXX
│   │   │   ├── AuditTrail.jsx          # Audit log table
│   │   │   ├── Login.jsx               # ⚠️ EMPTY (0 bytes)
│   │   │   └── AgentTrace.jsx          # ⚠️ EMPTY (0 bytes)
│   │   └── context/
│   │       └── AuthContext.jsx         # ⚠️ EMPTY (0 bytes)
```

---

## 8. Previously Fixed Bugs (B20–B25)

| Bug | Issue | Status |
|-----|-------|--------|
| B20 | Duplicate Supabase client in Ledger | ✅ Fixed — extracted to `utils/supabase_client.py` |
| B21 | Missing `langchain-google-genai` in requirements | ✅ Fixed |
| B22 | CORS_ORIGINS doesn't support multiple URLs | ✅ Fixed — splits on comma |
| B23 | Missing `requests` in requirements | ✅ Fixed |
| B24 | Missing `__init__.py` files | ✅ Fixed |
| B25 | Guardian `user_confirmed` false negatives | ✅ Fixed — deterministic override in `closer_node` |

---

## 9. 🐛 CURRENT BUGS & BREAKS (Full Report)

### 🔴 CRITICAL — App-Breaking

#### BUG-B26: Deprecated Embedding Model Crashes Chat
- **Component:** `backend/search/vector_store.py`
- **What:** `models/embedding-001` was removed from Google's API. Any chat message that triggers `search_catalog` tool → `embed_query()` → **404 NOT_FOUND** → **500 Internal Server Error**
- **Impact:** Chat is completely broken. The core feature of the app doesn't work.
- **Error:** `models/embedding-001 is not found for API version v1beta, or is not supported for embedContent`
- **Fix applied locally:** Changed to `models/gemini-embedding-001` + added keyword search fallback
- **Status:** 🟢 Fixed locally, 🔴 NOT deployed to Cloud Run yet

#### BUG-B30: Pinecone Index Dimension Mismatch
- **Component:** `backend/search/vector_store.py`
- **What:** Existing Pinecone index was created with `dimension=768` (old `embedding-001`), but `gemini-embedding-001` outputs 3072-dimension vectors. Upserting/querying will fail with dimension mismatch.
- **Impact:** Vector search is completely broken even with the new model.
- **Fix applied locally:** Added auto-detect logic to delete and recreate index on mismatch
- **Status:** 🟢 Fixed locally, 🔴 NOT deployed to Cloud Run yet

#### BUG-B33: Cloud Run Deployment Uses Old Code
- **Component:** Infrastructure
- **What:** The live Cloud Run deployment still has the old `models/embedding-001` code. All local fixes (B26, B30) need to be committed, pushed, and redeployed.
- **Impact:** Production backend is completely broken for chat.
- **Status:** 🔴 Open — needs `git push` + Cloud Run redeploy

---

### 🟠 HIGH — Major Feature Broken

#### BUG-B27: Frontend-Backend Chat Contract Mismatch
- **Component:** `frontend/src/pages/AgentChat.jsx` ↔ `backend/routes/chat.py`
- **What:** The frontend sends `session_id` (default `'guest'`) but the backend `ChatRequest` model expects `conversation_id`. Three sub-issues:
  1. **POST /chat/**: `conversation_id` is always `None` → new conversation created on every single message. History is lost on page reload.
  2. **GET /chat/history?session_id=guest**: Backend parameter is `conversation_id` (different name) → receives `None` → always returns `[]`. History never loads.
  3. **DELETE /chat/history?session_id=...**: Same mismatch → delete is a no-op.
- **Also:** The POST response returns `conversation_id` but the frontend never stores it or sends it back in subsequent messages.
- **Impact:** Chat appears to work in a single session but loses all history on refresh. "Clear Chat" button does nothing on the backend.
- **Status:** 🔴 Open

#### BUG-B28: Cloud Run Cold Start Timeout (~30s+)
- **Component:** Infrastructure (GCP Cloud Run free tier)
- **What:** Free-tier Cloud Run scales to 0 instances after inactivity. First request takes 30+ seconds to cold-start the Docker container. Frontend fetch calls time out.
- **Impact:** Users visiting the live site after idle period see "Failed to fetch catalog" / "Failed to fetch audit logs" errors.
- **Status:** 🟡 Known issue — needs `--min-instances=1` or frontend retry logic

---

### 🟡 MEDIUM — Feature Degraded

#### BUG-B29: CORS OPTIONS Preflight Returns 400
- **Component:** `backend/main.py` middleware
- **What:** `OPTIONS /catalog/` returns 400 Bad Request instead of 200 with CORS headers.
- **Root cause:** FastAPI middleware ordering. The comment in `main.py` says "Add GlobalError first, then RateLimit, then CORS" — but FastAPI applies middleware in reverse order, so CORS actually runs first (outermost). The issue may be that `RateLimitMiddleware` or `GlobalErrorMiddleware` is intercepting OPTIONS before CORS can handle it.
- **Impact:** Strict browsers may block cross-origin requests if preflight fails. Works intermittently.
- **Status:** 🟡 Open

#### BUG-B31: Three Frontend Files Are Empty (0 bytes)
- **Component:** Frontend
- **Files:**
  - `frontend/src/pages/Login.jsx` — 0 bytes
  - `frontend/src/pages/AgentTrace.jsx` — 0 bytes
  - `frontend/src/context/AuthContext.jsx` — 0 bytes
- **Impact:** Login page, Agent Trace viewer, and Auth context don't exist. JWT tokens from the backend can't be stored or sent with requests. The auth system is effectively disconnected from the frontend.
- **Status:** 🟡 Open — need to regenerate or rewrite

#### BUG-B34: CONTEXT.md is Stale
- **Component:** `CONTEXT.md` (project root)
- **What:** The "Current Status" section still says "PLANNING COMPLETE → READY TO BUILD" and "Last updated: 2026-08-24". Doesn't reflect Days 1-7 of actual development, deployment, or the current architecture.
- **Impact:** Any AI reading CONTEXT.md first will have incorrect context about project state.
- **Status:** 🟡 Open

#### BUG-B35: Frontend Doesn't Send JWT Auth Token
- **Component:** `frontend/src/pages/AgentChat.jsx`, `Catalog.jsx`, `AuditTrail.jsx`
- **What:** All frontend `fetch()` calls omit the `Authorization: Bearer <token>` header. The backend `auth_middleware.py` uses `auto_error=False` so it returns `None` (guest mode) instead of 401. This means:
  - Chat conversations aren't associated with a user
  - `/chat/conversations` always returns empty (no `user_id`)
  - Auth is effectively bypassed everywhere
- **Root cause:** `AuthContext.jsx` is 0 bytes (B31), so there's no auth provider wrapping the app
- **Impact:** Multi-user features don't work. All chats are anonymous/guest.
- **Status:** 🟡 Open

#### BUG-B36: Booster and Campaigner Agents Not Wired Into Graph
- **Component:** `backend/agents/maxx.py`
- **What:** `booster.py` and `campaigner.py` exist as files but are never imported or added as nodes in the MAXX LangGraph StateGraph. The graph only has `scout → tools → closer` routing.
- **Impact:** Upsell/cross-sell and campaign features are dead code. The agents exist but are never invoked.
- **Status:** 🟡 Open

---

### ⚪ LOW — Cosmetic / Housekeeping

#### BUG-B32: `fix_urls.py` Left in Repo Root
- **Component:** Repository root
- **What:** A one-off utility script that was used to update frontend API URLs is still committed to the repo.
- **Status:** 🟡 Open — delete or `.gitignore`

#### BUG-B37: `dev-notes.md` Says Backend Port 8000, Actual is 8002
- **Component:** `docs/dev-notes.md`
- **What:** Dev notes say "frontend runs on port 5173, backend on port 8000" but the backend has been running on port 8002 throughout development.
- **Status:** 🟡 Open

#### BUG-B38: `.env.example` Contains Real-Looking Keys
- **Component:** `.env.example`
- **What:** The `.env.example` file contains what appear to be actual API keys (Razorpay test keys, Supabase anon keys, etc.) instead of placeholder values like `your-key-here`. If these are real keys, they're exposed in the public repo.
- **Impact:** Security risk if keys are real and repo is public.
- **Status:** 🟡 Open — verify and rotate if needed

#### BUG-B39: No 404 Route / SPA Fallback on Vercel
- **Component:** Frontend deployment
- **What:** If a user navigates directly to `/chat` or `/audit` on Vercel (not via client-side routing), Vercel may return a 404 because there's no `vercel.json` with SPA rewrites in the frontend directory.
- **Status:** 🟡 Open — needs `vercel.json` with `{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }`

---

## 10. Priority Fix Roadmap

| Priority | Bug(s) | What To Do | Effort |
|----------|--------|------------|--------|
| 🔴 P0 | B33 | Push fixes + redeploy Cloud Run | 10 min |
| 🔴 P0 | B27 | Fix frontend to use `conversation_id` and persist it across messages | 30 min |
| 🟠 P1 | B31, B35 | Write `Login.jsx`, `AuthContext.jsx`, wrap app in auth provider, add Bearer headers | 1-2 hrs |
| 🟠 P1 | B28 | Set `--min-instances=1` on Cloud Run OR add frontend retry | 15 min |
| 🟡 P2 | B29 | Fix middleware ordering for CORS OPTIONS | 15 min |
| 🟡 P2 | B34 | Update `CONTEXT.md` with current state | 20 min |
| 🟡 P2 | B36 | Wire Booster/Campaigner into MAXX graph (or remove from plan) | 1 hr |
| 🟡 P2 | B39 | Add `vercel.json` for SPA fallback | 5 min |
| ⚪ P3 | B32 | Delete `fix_urls.py` | 1 min |
| ⚪ P3 | B37 | Fix port number in dev-notes | 1 min |
| ⚪ P3 | B38 | Rotate keys if real | 10 min |

---

*Last updated: 2026-08-27*
