# ✅ Task Tracker — Merchant Maxx

> Master checklist of all implementation tasks. Updated as work progresses.

---

## 🔴 Day 1 — Setup & Foundation

- [ ] Create Razorpay account at [dashboard.razorpay.com/signup](https://dashboard.razorpay.com/signup)
- [ ] Generate test-mode API keys (Settings → API Keys → Generate)
- [ ] Create Supabase project (free tier)
- [ ] Run Supabase schema migration (products, customers, orders, campaigns, audit_log, conversations)
- [ ] Scaffold FastAPI backend (`backend/`)
- [ ] Scaffold Vite + React frontend (`frontend/`)
- [ ] Create `.env.example` and `.env` with all config vars
- [ ] Install Python deps: `razorpay`, `litellm`, `langgraph`, `fastapi`, `uvicorn`, `supabase`, `pydantic-settings`
- [ ] Install JS deps: `react-router-dom`, `recharts`, `lucide-react`
- [ ] Verify Razorpay SDK connection (test API call)
- [ ] Verify Supabase connection
- [ ] Verify LLM connection (Gemini or Ollama)

## 🔴 Day 2 — Razorpay Client + Catalog

- [ ] Create `razorpay_service/client.py` — SDK wrapper with error handling
- [ ] Create `razorpay_service/items.py` — Items CRUD (create, fetch, list, delete)
- [ ] Create `razorpay_service/customers.py` — Customer CRUD
- [ ] Create `razorpay_service/orders.py` — Order create, fetch, list
- [ ] Create `razorpay_service/payments.py` — Payment fetch, capture
- [ ] Create `razorpay_service/payment_links.py` — Payment link generation
- [ ] Create `razorpay_service/refunds.py` — Refund processing
- [ ] Create `routes/catalog.py` — REST endpoints for catalog
- [ ] Seed 10-15 demo products (electronics: phones, headphones, chargers, cases, etc.)
- [ ] Sync products to Razorpay Items API + Supabase

## 🔴 Day 3 — ACP Protocol + Core Agents

- [ ] Create `acp/schemas.py` — Pydantic models for ACP protocol
- [ ] Create `acp/protocol.py` — `.well-known/agent-commerce.json` + all ACP endpoints
- [ ] Create `acp/discovery.py` — Product discovery & recommendation engine
- [ ] Create `agents/tools.py` — Shared tool definitions (JSON schemas per B.6)
- [ ] Create `agents/scout.py` — Discovery → compare → purchase intent
- [ ] Create `agents/closer.py` — Catalog management + pricing
- [ ] Create `agents/maxx.py` — LangGraph StateGraph connecting all agents
- [ ] Test: Scout discovers catalog via ACP endpoints

## 🔴 Day 4 — Guardian + Audit + Upsell/Campaign

- [ ] Create `agents/guardian.py` — Safety gate with constitutional rules
- [ ] Create `audit/constitutional.py` — Constitutional AI rules engine
- [ ] Create `agents/ledger.py` — Structured audit logging to Supabase (replacing audit/logger.py)
- [ ] Create `audit/evaluator.py` — LLM eval for agent decision quality
- [ ] Create `agents/booster.py` — Cross-sell recommendations
- [ ] Create `agents/campaigner.py` — Discount/offer campaigns
- [ ] Create `routes/audit.py` — Audit trail REST endpoints
- [ ] Test: Guardian blocks spending limit violation
- [ ] Test: Refund flow works end-to-end
- [ ] Test: Audit log captures every money action

## 🔴 Day 5 — Frontend: Dashboard + Chat + Catalog

- [ ] Create `index.css` — Design system (tokens, colors, typography, animations)
- [ ] Create `Navbar.jsx` — Navigation with glassmorphism
- [ ] Create `Dashboard.jsx` — Revenue chart, AI recommendations, campaign summary
- [ ] Create `RevenueChart.jsx` — Interactive chart component (recharts)
- [ ] Create `Chat.jsx` — Conversational checkout with SSE streaming
- [ ] Create `ChatMessage.jsx` — Message bubble component
- [ ] Create `Catalog.jsx` — Product grid with filters
- [ ] Create `ProductCard.jsx` — Product card component
- [ ] Create `CheckoutModal.jsx` — Razorpay Standard Checkout wrapper
- [ ] Integrate Razorpay Checkout.js in frontend

## 🔴 Day 6 — Frontend: Agent Simulator + Audit + Campaigns

- [ ] Create `AgentSimulator.jsx` — Real-time agent trace visualization
- [ ] Create `AgentTrace.jsx` — Step-by-step reasoning display
- [ ] Create `AuditLog.jsx` — Searchable audit trail table
- [ ] Create `AuditEntry.jsx` — Detailed audit entry with constitutional checks
- [ ] Create `Campaigns.jsx` — Campaign management + AI suggestions
- [ ] Add animations and micro-interactions
- [ ] Responsive layout for all pages

## 🔴 Day 7 — Integration Test + Demo Polish

- [ ] End-to-end: Agent-to-agent transaction flow
- [ ] End-to-end: Human conversational checkout
- [ ] End-to-end: Spending limit rejection → graceful failure
- [ ] End-to-end: Refund flow
- [ ] End-to-end: Upsell recommendation
- [ ] End-to-end: Campaign creation + activation
- [ ] Set up LangSmith tracing (optional)
- [ ] Create Dockerfile for backend
- [ ] Deploy backend to GCP Cloud Run
- [ ] Deploy frontend to Vercel
- [ ] Write README.md with setup instructions
- [ ] Record demo video (5-minute walkthrough)
- [ ] Test LLM provider switch (Gemini → Ollama)

---

*Legend: 🔴 Not started | 🟡 In progress | 🟢 Complete*

*Last updated: 2026-08-24*
