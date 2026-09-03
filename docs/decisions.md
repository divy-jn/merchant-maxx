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
# 📋 Architecture & Design Decisions — Merchant Maxx

> Every major design decision with context, options considered, and rationale.

---

## Decision 001: ACP-inspired Protocol (not full A2A)

**Date:** 2026-08-24 | **Status:** ✅ Decided

**Context:** The hackathon track mentions ACP, A2A, x402, and NPCI UAP. Need to pick which protocol to implement.

**Options:**
1. Full ACP spec compliance (complex, time-intensive)
2. Full Google A2A implementation (agent coordination, not commerce-focused)
3. **ACP-inspired REST endpoints** (practical, commerce-focused, buildable in 1 week)
4. x402 (HTTP 402 payment protocol — niche)

**Decision:** Option 3 — ACP-inspired REST endpoints with `.well-known/agent-commerce.json` discovery.

**Rationale:**
- ACP is the commerce-specific protocol (catalog → cart → checkout) — directly matches our use case
- Full spec compliance would eat too much time for a solo 1-week build
- Our ACP-inspired layer is **structurally compatible** with the real ACP spec (same endpoint patterns)
- A2A handles agent communication, which we handle internally via LangGraph
- Judges care about "working demo" not "spec compliance"

---

## Decision 002: LiteLLM as library, not proxy server

**Date:** 2026-08-24 | **Status:** ✅ Decided

**Context:** Need LLM provider abstraction for switching via .env.

**Options:**
1. Raw SDK calls (google-generativeai, openai, etc.) with if/else switching
2. LiteLLM proxy server (separate Docker container)
3. **LiteLLM Python library** (inline import, zero infra)

**Decision:** Option 3 — `pip install litellm`, use `litellm.completion()` in code.

**Rationale:**
- Zero infrastructure cost or setup
- Single `completion()` call works with Gemini, OpenAI, Ollama, Anthropic
- Model switching is literally changing an env var: `LLM_MODEL=gemini/gemini-2.0-flash`
- No extra container to manage in deployment

---

## Decision 003: GCP Cloud Run for backend deployment

**Date:** 2026-08-24 | **Status:** ✅ Decided

**Context:** Need to deploy for 1000+ concurrent users with free credits.

**Options:**
1. AWS EC2 ($100 credits, manual scaling, server management)
2. AWS Lambda + Mangum ($100 credits, need adapter, cold starts)
3. **GCP Cloud Run** ($300 credits, auto-scale, 1 command deploy)
4. Render free tier (limited, 512MB RAM, spins down after 15 min)
5. Railway ($5 free credits, limited)

**Decision:** Option 3 — GCP Cloud Run.

**Rationale:**
- **$300 free credits** (3x more than AWS)
- Auto-scales to 1000+ concurrent requests out of the box
- Dockerized FastAPI → `gcloud run deploy` (1 command)
- Scale-to-zero = no cost when idle
- Free custom domain mapping if needed

**Backup:** Render free tier for development, Cloud Run for production demo.

---

## Decision 004: Split deployment (Frontend CDN + Backend Cloud Run)

**Date:** 2026-08-24 | **Status:** ✅ Decided

**Context:** 1000+ users need the frontend to be fast globally.

**Decision:**
- **Frontend:** Vercel free tier (React build on CDN, globally distributed, infinite scale, free)
- **Backend:** GCP Cloud Run (auto-scaling containerized FastAPI)
- **Database:** Supabase free tier (managed Postgres, connection pooling)

**Rationale:** Separating static frontend from dynamic backend is standard for scale. Frontend on CDN means zero backend load for page loads — only API calls hit Cloud Run.

---

## Decision 005: razorpay-python SDK (not raw HTTP)

**Date:** 2026-08-24 | **Status:** ✅ Decided

**Context:** Need to integrate with Razorpay APIs.

**Decision:** Use official `razorpay` Python SDK (`pip install razorpay`).

**Rationale:**
- Official, maintained by Razorpay team
- Handles auth, retries, error parsing
- Supports all APIs: Orders, Payments, Items, Customers, Payment Links, Refunds
- Less code, fewer bugs than raw HTTP

---

## Decision 006: Domain strategy

**Date:** 2026-08-24 | **Status:** 🟡 Pending user input

**Options:**
1. **Free subdomain** — `agentbazaar.onrender.com` or `agentbazaar.vercel.app` (zero cost)
2. **GitHub Student Pack** — free `.tech` or `.me` domain for 1 year
3. **Buy cheap domain** — `.xyz` for ~$1/year

**Current recommendation:** Start with free Vercel/Render subdomain. Upgrade to custom domain later if desired.

---

## Decision 007: MAXX-only customer-facing agent

**Date:** 2026-08-25 | **Status:** ✅ Decided

**Context:** Users were seeing internal agent names (Scout, Closer) in chat responses, breaking the product illusion.

**Decision:** MAXX is the **only** customer/merchant-facing agent. All other agents (Scout, Closer, Booster, Campaigner, Guardian, Ledger) are internal and invisible.

**Rationale:**
- Customers should interact with a single, consistent AI personality
- Internal agents are implementation details — exposing them confuses users
- MAXX orchestrates silently; Scout searches, Closer executes payments, Guardian validates — all behind the scenes
- This mirrors how real products work (e.g., you talk to "Alexa", not "Alexa's NLU module")

---

## Decision 008: Simple session-based auth (in-memory)

**Date:** 2026-08-25 | **Status:** ✅ Decided

**Context:** Need user auth for chat history and role-based access (customer vs merchant).

**Options:**
1. JWT tokens with Supabase Auth (production-grade, complex setup)
2. **In-memory session store** with UUID session IDs (fast to build, swap later)
3. OAuth/Google Sign-In (requires Google Cloud Console setup)

**Decision:** Option 2 — In-memory session store for now. Designed to be swappable with Supabase Auth later.

**Rationale:**
- Fastest to implement for hackathon demo
- Session IDs are passed as query params / request body
- Easy to migrate to JWT or Supabase Auth for production
- Demo user seeded automatically on server start

---

## Decision 009: In-memory chat history per session

**Date:** 2026-08-25 | **Status:** ✅ Decided

**Context:** MAXX needs conversation context to have coherent multi-turn conversations.

**Decision:** Store chat history in-memory, keyed by session ID. Last 20 messages retained per session.

**Rationale:**
- LangGraph needs full message history for context-aware responses
- 20-message window prevents token overflow while maintaining context
- History endpoints (`GET /chat/history`, `DELETE /chat/history`) for frontend persistence
- Can migrate to Supabase persistence for production

---

## Decision 010: Server-authoritative purchase state via `purchase_intents`

**Date:** 2026-08-27 | **Status:** ✅ Decided

**Context:** LLM-managed state was unreliable — agents could hallucinate `user_confirmed=True` or supply incorrect amounts. Purchase state needed to survive server restarts and be tamper-proof.

**Options:**
1. Keep state in LangGraph `AgentState` only (in-memory, LLM-mutable)
2. **Persist authoritative state in Supabase `purchase_intents` table** (server-side, loaded/saved per chat turn)
3. Use Redis for ephemeral state (fast but volatile)

**Decision:** Option 2 — Supabase `purchase_intents` as single source of truth.

**Rationale:**
- Chat route loads existing intent on each turn, passes it to LangGraph as read-only context
- After LangGraph runs, route persists updated state back to Supabase
- Guardian reads `user_confirmed` and `amount_paise` from DB, not LLM state
- Webhooks use `purchase_intent_id` (stored as Razorpay order receipt) for attribution
- Survives server restarts, multi-instance deployments, and LLM hallucinations

---

## Decision 011: Scoped tool sets per agent

**Date:** 2026-08-27 | **Status:** ✅ Decided

**Context:** All agents previously had access to all tools via `DISCOVERY_TOOLS` and `PAYMENT_TOOLS` with loose boundaries.

**Decision:** Split tools into scoped sets — `SCOUT_TOOLS`, `BOOSTER_TOOLS`, `CAMPAIGNER_TOOLS`, `PAYMENT_TOOLS`. Each agent binds only its own tools.

**Rationale:**
- Principle of least privilege — Scout can't create orders, Closer can't search catalog
- Reduces LLM confusion from irrelevant tool descriptions
- Makes Guardian violations easier to detect (wrong tool usage = wrong agent)
- `confirm_and_pay` was a no-op placebo tool; replaced with real `check_payment_status`

---

*Last updated: 2026-08-27*
