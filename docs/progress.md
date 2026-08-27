# 📊 Daily Progress Journal — Merchant Maxx

> Day-by-day log of what was done, blockers, and next steps.

---

## Day 0 — Planning & Research (2026-08-24)

### ✅ Completed
- [x] Defined project scope: multi-agent agentic commerce platform
- [x] Researched Razorpay APIs: Orders, Payments, Items, Customers, Payment Links, Refunds
- [x] Studied Razorpay AI Playbook (B.5 multi-agent orchestration, G.22-G.28 fintech guardrails)
- [x] Found official `razorpay-python` SDK — using this instead of raw HTTP
- [x] Researched ACP vs A2A vs MCP protocol stack — using ACP-inspired layer
- [x] Confirmed LiteLLM is free (MIT, open-source library)
- [x] Evaluated deployment: GCP Cloud Run ($300 credits, auto-scales to 1000+)
- [x] Evaluated free domains: GitHub Student Pack, Vercel/Render subdomains
- [x] Created implementation plan v2 (with Razorpay insights)
- [x] Created docs/ folder with full tracking structure
- [x] Resolved all initial Q&A (ACP vs A2A, LiteLLM pricing, deployment, scaling)

### 🚧 Blockers
- Need Razorpay test-mode API keys (user needs to create account)
- Need Supabase project (can create via MCP tools)
- Need Gemini API key or Ollama setup

### 📌 Next Steps (Day 1)
- [ ] Create Razorpay account + generate test API keys
- [ ] Create Supabase project + run schema migrations
- [ ] Scaffold FastAPI backend + Vite React frontend
- [ ] Install core dependencies (razorpay, litellm, langgraph, fastapi)
- [ ] Set up .env configuration

---

## Day 1 — Setup & Foundation (2026-08-24)
*Status: 🟢 Complete*

### ✅ Completed
- [x] Received Razorpay test keys and Gemini/Ollama keys
- [x] Received Supabase connection URL and password
- [x] Scaffolded FastAPI backend + Vite React frontend
- [x] Created `backend/db/schema.sql` migration script for Supabase
- [x] Installed Python dependencies (razorpay, litellm, langgraph, fastapi, supabase)
- [x] Installed JS dependencies (react-router-dom, recharts, lucide-react)
- [x] Created `.env` and `.env.example`
- [x] Committed Day 1 changes to GitHub

### 📌 Next Steps (Day 2)
- [ ] Create Razorpay SDK wrapper
- [ ] Create catalog REST endpoints
- [ ] Seed demo products

## Day 2 — Razorpay Client + Catalog (2026-08-24)
*Status: 🟢 Complete*

### ✅ Completed
- [x] Built Razorpay SDK wrappers with error handling (`client.py`, `items.py`, `customers.py`, `orders.py`, `payments.py`, `payment_links.py`, `refunds.py`)
- [x] Fixed Razorpay nested `item` payload format issue
- [x] Created `routes/catalog.py` REST endpoints for listing and creating items
- [x] Wrote `scripts/seed_products.py` to seed 10 demo electronics products
- [x] Successfully populated Razorpay test account with the demo products
- [x] Committed Day 2 code to local git repository

### 📌 Next Steps (Day 3)
- [ ] Build ACP Protocol Layer (`acp/schemas.py`, `acp/protocol.py`, `acp/discovery.py`)
- [ ] Build Agent Tools (`agents/tools.py`)
- [ ] Build Scout Agent (`agents/scout.py`)
- [ ] Build Closer Agent (`agents/closer.py`)
- [ ] Build MAXX Orchestrator (`agents/maxx.py`)

## Day 3 — ACP Protocol + Core Agents (2026-08-24)
*Status: 🟢 Complete*

### ✅ Completed
- [x] Built the **Agent Commerce Protocol (ACP)** Layer (`acp/schemas.py`, `acp/protocol.py`, `acp/discovery.py`)
- [x] Defined service discovery `.well-known/agent-commerce.json` endpoint
- [x] Built **Scout Agent** for discovering intent and answering catalog queries
- [x] Built **Closer Agent** for executing purchases and generating payment links
- [x] Built **MAXX Orchestrator** using LangGraph to connect Scout and Closer
- [x] Defined agent tools for searching catalog and generating links in `agents/tools.py`
- [x] Added `/chat/` endpoint to test conversational flow
- [x] Committed code without specific day tags per user request

### 📌 Next Steps (Day 4)
- [ ] Build **Guardian Agent** (Safety Gate with constitutional rules)
- [ ] Build **Ledger Agent** for structured audit logging
- [ ] Build **Booster Agent** for upsell/cross-sell
- [ ] Build **Campaigner Agent** for discount generation
- [ ] Build Audit APIs

## Day 4 — Guardian + Audit + Upsell/Campaign (2026-08-24)
*Status: 🟢 Complete*

### ✅ Completed
- [x] Built the **Guardian Agent** (`agents/guardian.py`) as a deterministic & AI-based safety gate.
- [x] Integrated Guardian into tools to block money actions (like link creation) without user confirmation.
- [x] Built the **Ledger Agent** (`agents/ledger.py`) for immutable audit logging to Supabase.
- [x] Created `audit/constitutional.py` and `audit/evaluator.py` for safety rule validation.
- [x] Built the **Booster Agent** (`agents/booster.py`) for smart cross-sells.
- [x] Built the **Campaigner Agent** (`agents/campaigner.py`) for intelligent discounting.
- [x] Added REST API routes in `routes/audit.py` to view the audit logs.
- [x] Pushed all code to GitHub (without explicit Day tags).

### 📌 Next Steps (Day 5)
- [ ] Build Frontend Dashboard (React + Vite)
- [ ] Implement Chat UI for MAXX agent
- [ ] Build UI to display Product Catalog
- [ ] Implement Audit Trail viewer UI
- [ ] Test End-to-End flow via UI

## Day 5 — Frontend: Dashboard + Chat + Catalog (2026-08-24)
*Status: 🟢 Complete*

### ✅ Completed
- [x] Set up React + Vite frontend with `lucide-react` icons.
- [x] Implemented a stunning glassmorphism dark mode theme (`index.css`).
- [x] Created `DashboardLayout` with a sleek sidebar navigation.
- [x] Created `Catalog` view that fetches and displays products from the FastAPI backend.
- [x] Created `AgentChat` interface to talk directly to MAXX and the AI orchestrator.
- [x] Created `AuditTrail` view to display the immutable Ledger logs.
- [x] Started both Vite (port 5173) and Uvicorn (port 8000) dev servers.
- [x] Pushed all frontend code to GitHub.

### 📌 Next Steps (Day 6)
- [ ] Implement Razorpay Checkout.js for instant payments via Plinks.
- [ ] Build Agent Simulator UI for observing internal AI reasoning.
- [ ] Build Campaigns Dashboard for Booster/Campaigner logic.
- [ ] End-to-end polish and cleanup.

## Day 6 — Architecture Refactor + Auth + Chat History (2026-08-25)
*Status: 🟢 Complete*

### ✅ Completed
- [x] **Architecture refactor:** MAXX is now the only customer-facing agent
- [x] All internal agents (Scout, Closer, Booster, Campaigner) updated to never reveal their identity
- [x] Added session-based user auth system (`routes/auth.py` — register, login, session management)
- [x] Added chat history persistence per session (last 20 messages retained)
- [x] Added `GET /chat/history` and `DELETE /chat/history` endpoints
- [x] Updated Chat UI: only shows "MAXX" label, added Clear Chat button
- [x] Updated `decisions.md` with Decisions 007, 008, 009
- [x] Demo user seeded automatically (`demo@merchantmaxx.com` / `demo123`)
- [x] Added LangSmith MCP server to IDE configuration (`mcp_config.json`)
- [x] Enabled automatic LangChain / LangGraph tracing to LangSmith project `merchant-maxx`
- [x] Fix pre-existing bugs (B20-B25)
- [x] Implement GlobalErrorMiddleware to safely catch exceptions
- [x] Implement RateLimitMiddleware using Upstash Redis

## Day 7 — Phase 3: Resilience, State Integrity & Attribution (2026-08-27)
*Status: 🟡 In Progress*

### ✅ Completed
- [x] **`purchase_intents` table** — new Supabase table to persist authoritative purchase state across sessions (`schema.sql`)
- [x] **Chat route overhauled** (`routes/chat.py`) — loads/saves purchase state from Supabase `purchase_intents` on every turn, ensuring server-authoritative state survives restarts
- [x] **Webhook handler rewritten** (`routes/webhooks.py`):
  - Idempotency checks on both `payment.captured` and `payment.failed` events
  - Maps Razorpay Order ID → local `order_id` via `entity_mapping`
  - Records payment in `payments` table, updates `orders.status`
  - Revenue attribution via `purchase_intent_id` receipt → `recommendation_events` CONVERTED
  - Failed-payment handling with `FAILED` status propagation
- [x] **Guardian constitutional hardening** (`audit/constitutional.py`):
  - Added `auth_intent` parameter for server-side authoritative state checks
  - RULE_05 now checks for existing `razorpay_order_id` (real idempotency vs flag-based)
  - RULE_07 (new): Amount-match validation — requested amount must match authoritative intent
  - RULE_02 reads `user_confirmed` from authoritative state, not LLM state
- [x] **Tool refactoring** (`agents/tools.py`):
  - Scoped tool sets: `SCOUT_TOOLS`, `BOOSTER_TOOLS`, `CAMPAIGNER_TOOLS`, `PAYMENT_TOOLS`
  - `stage_purchase_intent` no longer takes `amount_paise` — system determines price authoritatively
  - `confirm_and_pay` removed; replaced by `check_payment_status` for FAILED/UNKNOWN recovery
  - `create_razorpay_order` now creates local `orders`, `order_items`, and `entity_mapping` rows
  - `fetch_recommendations` uses `lift_score > 1.0` threshold with same-category fallback
  - `analyze_campaign_opportunities` uses correct `lifetime_value_paise` column
- [x] **Scout agent** (`agents/scout.py`):
  - Binds `SCOUT_TOOLS` instead of `DISCOVERY_TOOLS`
  - Authoritatively fetches item price from Razorpay on `stage_purchase_intent` (no LLM-supplied amounts)
  - Tracks `recommendation_id` through to basket items; updates `recommendation_events` to ACCEPTED
- [x] **MAXX orchestrator** (`agents/maxx.py`):
  - Compiled with `MemorySaver` checkpointer for multi-turn conversational continuity
  - Expanded campaigner routing heuristic (`metrics`, `uplift`, `vip`, `churn`)
  - Added `PURCHASE_PENDING` to Closer routing states
  - Defensive `.get()` on messages to prevent KeyError
  - Tool routing updated: `search_catalog`, `stage_purchase_intent`, `check_payment_status`, `analyze_campaign_opportunities`
- [x] **Closer & Booster minor fixes** — updated to match new tool API signatures
- [x] **Guardian agent** (`agents/guardian.py`) — passes `auth_intent` to constitutional evaluator

### 📌 Next Steps
- [ ] Guardian rules pass unit tests
- [ ] **E2E Test 1**: Happy-path Razorpay Test Mode transaction
- [ ] **E2E Test 2**: FAILED/UNKNOWN recovery scenario
- [ ] Demo polish and final cleanup

---

*Last updated: 2026-08-27*
