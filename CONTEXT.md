# 🧠 PROJECT CONTEXT — Merchant Maxx

> **READ THIS FIRST.** This file is the single source of truth for any human or AI working on this project.
> If you're an LLM (ChatGPT, Claude, Gemini, Cursor, Copilot, or any other AI assistant), read this file completely before touching any code.

---

## What is this project?

**Merchant Maxx** is a multi-agent AI commerce platform built for the **Razorpay AI Hackathon (Track 01: AI Growth & Agentic Commerce)**. It demonstrates:

1. **AI agents that autonomously buy products** using Razorpay test-mode APIs
2. **Conversational checkout** where humans chat with an AI to discover and buy products
3. **Revenue growth engine** with AI-powered upsell, cross-sell, and campaign agents
4. **Safety gates** (Guardian) that validate every money action before execution
5. **Full audit trail** (Ledger) with explainable reasoning for every agent decision

---

## Project Owner

- **Name:** Divy Jain
- **Email:** divyjn28@gmail.com
- **GitHub:** [github.com/divy-jn](https://github.com/divy-jn)
- **Repo:** [github.com/divy-jn/merchant-maxx](https://github.com/divy-jn/merchant-maxx) (private)
- **Role:** Solo developer

---

## Agent Naming System

| Code Name | Role | What it does |
|-----------|------|-------------|
| **MAXX** | Master Orchestrator | Routes intents to the right specialist agent |
| **Scout** | Discovery & Intent | Discovers products, understands buyer intent, finds opportunities |
| **Closer** | Checkout & Purchase | Executes purchases — creates orders, processes payments |
| **Booster** | Upsell & Cross-sell | Suggests complementary products to increase AOV |
| **Campaigner** | Campaign Engine | Generates and executes discount/offer campaigns |
| **Guardian** | Safety Gate | Validates EVERY money action against constitutional rules |
| **Ledger** | Audit & Explainability | Logs every decision with reasoning, risk scores, traces |

---

## Tech Stack (do NOT change without updating this file)

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend | React + Vite | React 18+, Vite 5+ | UI framework |
| Styling | Vanilla CSS with design tokens | — | Premium aesthetic, no Tailwind |
| Backend | Python FastAPI | 3.11+, FastAPI 0.100+ | Async API server |
| Multi-Agent | LangGraph | Latest | State machine for 7 agents |
| LLM Gateway | LiteLLM (Python library) | Latest | Switch providers via `.env` |
| Database | Supabase PostgreSQL | Free tier | Managed Postgres + real-time |
| Payments | `razorpay` Python SDK | Latest | Official Razorpay SDK |
| Checkout | Razorpay Standard Checkout JS | Latest | Payment modal in frontend |
| Protocol | ACP-inspired REST endpoints | Custom | Agent-readable commerce API |
| Observability | LangSmith + Ledger agent | Free tier | LLM traces + audit log |
| Deploy (BE) | GCP Cloud Run | — | Auto-scaling containers |
| Deploy (FE) | Vercel | Free tier | CDN-distributed frontend |

---

## Architecture (7 Agents — the MAXX System)

```
User/AI Buyer → FastAPI → MAXX (Orchestrator)
                              ├── Scout        (discover, compare, find opportunities)
                              ├── Closer       (checkout, create order, process payment)
                              ├── Booster      (upsell, cross-sell, AOV growth)
                              ├── Campaigner   (discounts, offers, campaign management)
                              ├── Guardian     (SAFETY GATE — validates ALL money actions)
                              └── Ledger       (audit trail, explainability, risk scoring)
                                    ↓
                              Razorpay SDK (test mode) → Supabase (persistent storage)
```

**Critical rules:**
- EVERY money action (payment, refund, order) MUST pass through **Guardian** before execution
- EVERY agent decision MUST be logged by **Ledger** with reasoning and risk score
- **MAXX** never executes money actions directly — it delegates to specialists

---

## Directory Structure

```
merchant-maxx/
├── CONTEXT.md              ← YOU ARE HERE (read first)
├── .env                    # Local secrets (NEVER commit)
├── .env.example            # Template for .env
├── .gitignore
├── README.md               # Public-facing project README
├── docs/                   # All project tracking documents
│   ├── README.md           # Index of docs
│   ├── plan.md             # Step-by-step execution plan (👤 YOU / 🤖 AI)
│   ├── tasks.md            # Task tracker (TODO/Done)
│   ├── decisions.md        # Architecture decision records
│   ├── qna.md              # Q&A from planning
│   ├── bugs.md             # Bug tracker
│   ├── progress.md         # Daily progress journal
│   ├── deployment.md       # Deployment & infra guide
│   ├── dev-notes.md        # Command reference & gotchas
│   └── chat-history.md     # Conversation log
├── backend/
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Pydantic Settings (reads .env)
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile          # Container for Cloud Run
│   ├── agents/             # The MAXX multi-agent system
│   │   ├── maxx.py         # MAXX — master orchestrator (LangGraph state machine)
│   │   ├── scout.py        # Scout — discovery & intent agent
│   │   ├── closer.py       # Closer — checkout & purchase agent
│   │   ├── booster.py      # Booster — upsell & cross-sell agent
│   │   ├── campaigner.py   # Campaigner — campaign engine agent
│   │   ├── guardian.py     # Guardian — safety gate agent
│   │   ├── ledger.py       # Ledger — audit & explainability agent
│   │   └── tools.py        # Shared tool definitions (JSON schemas)
│   ├── acp/                # ACP-inspired protocol layer
│   │   ├── protocol.py     # .well-known + ACP endpoints
│   │   ├── schemas.py      # Pydantic models
│   │   └── discovery.py    # Product discovery engine
│   ├── razorpay_service/   # Razorpay SDK wrapper
│   │   ├── client.py       # SDK initialization
│   │   ├── orders.py       # Orders API
│   │   ├── payments.py     # Payments API
│   │   ├── items.py        # Items/Catalog API
│   │   ├── customers.py    # Customers API
│   │   ├── payment_links.py # Payment Links API
│   │   └── refunds.py      # Refunds API
│   ├── db/                 # Database layer
│   │   ├── supabase_client.py
│   │   └── models.py
│   └── routes/             # API route handlers
│       ├── catalog.py, checkout.py, chat.py, dashboard.py
│       ├── audit.py, agent_sim.py, webhooks.py
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── App.jsx          # Router + layout
│       ├── index.css        # Design system tokens
│       ├── pages/           # 6 pages: Dashboard, Chat, Catalog,
│       │                    #   AgentSimulator, AuditLog, Campaigns
│       ├── components/      # Reusable UI components
│       └── utils/api.js     # Backend API client
```

---

## Current Status

> **Update this section every time you make progress.**

- **Phase:** PLANNING COMPLETE → READY TO BUILD
- **Last updated:** 2026-08-24
- **What's done:** Full plan, docs, architecture, research, naming, GitHub repo
- **What's next:** Day 1 — Setup & Foundation (see docs/tasks.md)
- **Blockers:** Need Razorpay test keys + Supabase project + Gemini API key

---

## How to Run (once built)

```bash
# Backend — starts FastAPI dev server on http://localhost:8000
cd backend
pip install -r requirements.txt    # Install Python dependencies
uvicorn main:app --reload          # Start server with auto-reload

# Frontend — starts Vite dev server on http://localhost:5173
cd frontend
npm install                        # Install JavaScript dependencies
npm run dev                        # Start dev server
```

---

## Key Conventions (for any AI or human working on this)

1. **Commands:** Always explain what a command does in 1 line before running it
2. **Docs:** Update `docs/progress.md` after each work session
3. **Docs:** Update `docs/tasks.md` as items are completed
4. **Docs:** Log bugs in `docs/bugs.md` immediately when found
5. **Docs:** Record design decisions in `docs/decisions.md`
6. **Git:** Commit after each logical chunk of work with descriptive messages
7. **Git:** Push to `github.com/divy-jn/merchant-maxx` (private repo)
8. **Env:** ALL secrets go in `.env` — switch LLM provider by changing env vars only
9. **Razorpay:** Always use TEST MODE (`rzp_test_` prefix keys). Never use live keys.
10. **Guardian:** Every payment/refund/order MUST flow through Guardian agent
11. **Ledger:** Every agent decision MUST be logged with reasoning + risk score
12. **Amounts:** Razorpay uses PAISE (₹500 = 50000 paise). Always convert.
13. **Naming:** Use agent code names (MAXX, Scout, Closer, Booster, Campaigner, Guardian, Ledger) consistently everywhere

---

## For Other LLMs / AI Assistants

If you're a different AI tool continuing this project:

1. **Read this file first** — it has everything you need
2. **Read `docs/tasks.md`** — see what's done and what's pending
3. **Read `docs/progress.md`** — see the latest session's work
4. **Read `docs/plan.md`** — the step-by-step execution blueprint
5. **Read `docs/decisions.md`** — understand WHY things were built a certain way
6. **Read `docs/bugs.md`** — known issues to be aware of
7. **Follow the conventions above** — especially the 1-line command explanations and docs updates
8. **Update `docs/chat-history.md`** — log your session so the next AI has context
9. **Use agent names consistently:** MAXX, Scout, Closer, Booster, Campaigner, Guardian, Ledger

---

## Environment Variables Reference

```env
# LLM — change ONLY these to switch providers
LLM_PROVIDER=gemini              # gemini | openai | ollama | anthropic
LLM_MODEL=gemini-2.0-flash      # Model name for the chosen provider
LLM_API_KEY=xxx                  # Not needed for ollama
LLM_BASE_URL=                   # Only for custom endpoints (ollama: http://localhost:11434)

# Razorpay — test mode only
RAZORPAY_KEY_ID=rzp_test_xxxx
RAZORPAY_KEY_SECRET=xxxx

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_KEY=xxx

# Guardian safety limits
GUARDIAN_MAX_TRANSACTION_PAISE=1000000  # ₹10,000 max per transaction
GUARDIAN_DAILY_BUDGET_PAISE=5000000    # ₹50,000 daily budget
```
