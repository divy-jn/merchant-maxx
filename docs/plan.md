# 🚀 Merchant Maxx — Step-by-Step Execution Plan

> **How to read this:** Each step is marked with who does it:
> - 👤 **YOU** = Manual action by Divy (create accounts, click buttons, paste keys)
> - 🤖 **AI** = I do this (write code, run commands, configure)
> - 🤝 **BOTH** = We do this together (you confirm, I execute)

---

## Pre-Day 1: Accounts & Prerequisites

> These are one-time setups you need to do in your browser. I can't do these for you because they need your personal logins.

### Step 0.1 — 👤 YOU: Create Razorpay Account
1. Go to [dashboard.razorpay.com/signup](https://dashboard.razorpay.com/signup)
2. Sign up with your email (divyjn28@gmail.com)
3. **Don't need KYC for test mode** — just sign up
4. Go to Settings → API Keys → Generate Key
5. Copy both: `Key ID` (starts with `rzp_test_`) and `Key Secret`
6. **Paste them here in chat** — I'll put them in `.env`

### Step 0.2 — 👤 YOU: Get Gemini API Key
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click "Create API Key"
3. Copy the key
4. **Paste it here in chat** — I'll put them in `.env`

### Step 0.3 — 🤖 AI: Create Supabase Project
- I'll create this using Supabase MCP tools (already connected)
- You just confirm the project name

### Step 0.4 — 🤖 AI: Create GitHub Repository
- I'll create `merchant-maxx` repo under your GitHub account
- You need to confirm your GitHub username

---

## Day 1: Setup & Foundation

### Step 1.1 — 🤖 AI: Initialize GitHub Repo
**What:** Creates a new GitHub repository for version control and collaboration
```
I will create repo "merchant-maxx" with description, .gitignore, README
```

### Step 1.2 — 🤖 AI: Scaffold Backend (FastAPI)
**What:** Creates the Python backend folder with all files, dependencies, and folder structure
```
Creates: backend/main.py, config.py, requirements.txt, .env.example
Creates: backend/agents/, acp/, razorpay_service/, db/, audit/, routes/
```

### Step 1.3 — 🤖 AI: Scaffold Frontend (React + Vite)
**What:** Creates a React frontend project using Vite build tool
```bash
npx create-vite@latest ./frontend -- --template react
# Creates a new React project in the frontend/ folder using Vite
```

### Step 1.4 — 🤖 AI: Install Backend Dependencies
**What:** Installs all Python packages the backend needs
```bash
pip install razorpay litellm langgraph fastapi uvicorn supabase pydantic-settings python-dotenv
# razorpay    = Official Razorpay SDK for payments
# litellm     = LLM gateway (switch providers via .env)
# langgraph   = Multi-agent state machine
# fastapi     = Async web framework
# uvicorn     = ASGI server to run FastAPI
# supabase    = Database client
# pydantic-settings = Read .env into typed config
```

### Step 1.5 — 🤖 AI: Install Frontend Dependencies
**What:** Installs JavaScript packages for the frontend UI
```bash
cd frontend && npm install react-router-dom recharts lucide-react
# react-router-dom = Page routing (Dashboard, Chat, Catalog, etc.)
# recharts         = Revenue charts and data visualization
# lucide-react     = Beautiful icon library
```

### Step 1.6 — 🤝 BOTH: Configure .env
**What:** Sets up all API keys and configuration
- 👤 YOU: Paste Razorpay keys + Gemini key
- 🤖 AI: Creates `.env` file with all values

### Step 1.7 — 🤖 AI: Create Supabase Tables
**What:** Sets up the database schema (products, orders, customers, audit_log, etc.)
```
Creates 6 tables: products, customers, orders, campaigns, audit_log, conversations
```

### Step 1.8 — 🤖 AI: Verify All Connections
**What:** Tests that Razorpay, Supabase, and LLM are all reachable
```bash
python -c "import razorpay; print('Razorpay OK')"
# Verifies the Razorpay SDK is installed and importable

python -c "from supabase import create_client; print('Supabase OK')"
# Verifies the Supabase client can be imported

python -c "import litellm; print('LiteLLM OK')"
# Verifies LiteLLM is installed for LLM gateway
```

### Step 1.9 — 🤖 AI: Git Commit + Push
**What:** Saves all Day 1 work to GitHub
```bash
git add . && git commit -m "Day 1: Project scaffold + dependencies + env config"
git push origin main
```

### Step 1.10 — 🤖 AI: Update Docs
**What:** Updates progress.md, tasks.md, and chat-history.md with Day 1 status

---

## Day 2: Razorpay Client + Product Catalog

### Step 2.1 — 🤖 AI: Build Razorpay SDK Wrapper
**What:** Creates a clean wrapper around the official SDK with error handling and retry logic
```
Creates: backend/razorpay_service/client.py — SDK initialization
Creates: backend/razorpay_service/items.py — Product CRUD
Creates: backend/razorpay_service/orders.py — Order management
Creates: backend/razorpay_service/payments.py — Payment handling
Creates: backend/razorpay_service/customers.py — Customer management
Creates: backend/razorpay_service/refunds.py — Refund processing
Creates: backend/razorpay_service/payment_links.py — Payment links
```

### Step 2.2 — 🤖 AI: Create Catalog API Routes
**What:** REST endpoints for browsing/managing the product catalog
```
Creates: backend/routes/catalog.py
Endpoints: GET /catalog, GET /catalog/{id}, POST /catalog, PUT /catalog/{id}
```

### Step 2.3 — 🤖 AI: Seed Demo Products
**What:** Populates the store with 12-15 electronics products (phones, headphones, chargers, etc.)
```
Seeds products into both Supabase AND Razorpay Items API
Each product has: name, description, price, category, image
```

### Step 2.4 — 🤝 BOTH: Verify Catalog
- 🤖 AI: Runs the backend and opens the catalog endpoint
- 👤 YOU: Check `http://localhost:8000/catalog` in your browser — see products list

### Step 2.5 — 🤖 AI: Git Commit + Push + Update Docs

---

## Day 3: ACP Protocol + Core Agents

### Step 3.1 — 🤖 AI: Build ACP Protocol Layer
**What:** Creates the agent-readable commerce API with `.well-known` discovery
```
Creates: backend/acp/schemas.py — Pydantic models for ACP
Creates: backend/acp/protocol.py — All ACP endpoints
Creates: backend/acp/discovery.py — Product recommendation engine
Endpoint: GET /.well-known/agent-commerce.json — service discovery
```

### Step 3.2 — 🤖 AI: Build Buyer Agent
**What:** AI agent that discovers products, compares them, and decides what to buy
```
Creates: backend/agents/scout.py
Tools: search_catalog, get_product, add_to_cart, get_recommendations
```

### Step 3.3 — 🤖 AI: Build Seller Agent
**What:** AI agent that manages the merchant's catalog and pricing
```
Creates: backend/agents/closer.py
Tools: create_item, update_item, list_items, set_price
```

### Step 3.4 — 🤖 AI: Build Agent Tools
**What:** Shared tool definitions with JSON schemas (per Razorpay B.6 patterns)
```
Creates: backend/agents/tools.py — All tool contracts
```

### Step 3.5 — 🤖 AI: Build LangGraph Orchestrator
**What:** The state machine that routes messages to the right agent
```
Creates: backend/agents/maxx.py
Flow: Receive Intent → Route → Agent → Guardian → Execute/Reject
```

### Step 3.6 — 🤝 BOTH: Test Agent Discovery
- 🤖 AI: Runs buyer agent against catalog
- 👤 YOU: Watch the agent discover and select products in terminal output

### Step 3.7 — 🤖 AI: Git Commit + Push + Update Docs

---

## Day 4: Guardian + Audit + Upsell + Campaign

### Step 4.1 — 🤖 AI: Build Guardian Agent (THE SAFETY GATE)
**What:** The agent that validates EVERY money action before execution — the hackathon's key requirement
```
Creates: backend/agents/guardian.py
Rules: spending limits, constitutional checks, amount validation
Output: approve/reject with full reasoning + risk score
```

### Step 4.2 — 🤖 AI: Build Constitutional AI Rules
**What:** The safety rules that the Guardian enforces (inspired by Razorpay Playbook G.22-G.28)
```
Creates: backend/audit/constitutional.py
8 rules: spending limits, PII protection, confirmation required, etc.
```

### Step 4.3 — 🤖 AI: Build Audit Logger
**What:** Structured logging of every agent decision to Supabase
```
Creates: backend/agents/ledger.py
Logs: agent name, action, reasoning, risk score, Razorpay entity ID
```

### Step 4.4 — 🤖 AI: Build Upsell Agent
**What:** AI agent that suggests complementary products to increase average order value
```
Creates: backend/agents/booster.py
Tools: analyze_cart, get_purchase_history, find_complementary
```

### Step 4.5 — 🤖 AI: Build Campaign Agent
**What:** AI agent that creates/manages discount campaigns
```
Creates: backend/agents/campaigner.py
Tools: create_campaign, apply_discount, get_active_campaigns
```

### Step 4.6 — 🤖 AI: Build Audit API Routes
**What:** REST endpoints for viewing the audit trail
```
Creates: backend/routes/audit.py
Endpoints: GET /audit, GET /audit/{id}, GET /audit/stats
```

### Step 4.7 — 🤝 BOTH: Test Failure Handling
- 🤖 AI: Triggers a spending limit violation to demonstrate Guardian rejection
- 👤 YOU: See the rejection in the audit log with full reasoning

### Step 4.8 — 🤖 AI: Git Commit + Push + Update Docs

---

## Day 5: Frontend — Dashboard + Chat + Catalog

### Step 5.1 — 🤖 AI: Build Design System
**What:** CSS design tokens (colors, fonts, spacing) for a premium look
```
Creates: frontend/src/index.css — Full design system
Theme: Dark mode with glassmorphism, gradients, micro-animations
Font: Inter from Google Fonts
```

### Step 5.2 — 🤖 AI: Build Navigation
**What:** Sidebar/navbar connecting all 6 pages
```
Creates: frontend/src/components/Navbar.jsx
Creates: frontend/src/App.jsx — React Router setup
```

### Step 5.3 — 🤖 AI: Build Dashboard Page
**What:** Revenue charts, AI recommendations, campaign summary, key metrics
```
Creates: frontend/src/pages/Dashboard.jsx
Creates: frontend/src/components/RevenueChart.jsx
Uses: recharts for data visualization
```

### Step 5.4 — 🤖 AI: Build Chat Page (Conversational Checkout)
**What:** Chat interface with streaming AI responses
```
Creates: frontend/src/pages/Chat.jsx
Creates: frontend/src/components/ChatMessage.jsx
Uses: Server-Sent Events (SSE) for token-by-token streaming
```

### Step 5.5 — 🤖 AI: Build Catalog Page
**What:** Product grid with filters and Razorpay checkout button
```
Creates: frontend/src/pages/Catalog.jsx
Creates: frontend/src/components/ProductCard.jsx
Creates: frontend/src/components/CheckoutModal.jsx
Integrates: Razorpay Standard Checkout JS
```

### Step 5.6 — 🤝 BOTH: Visual Review
- 🤖 AI: Starts frontend dev server
- 👤 YOU: Open `http://localhost:5173` and browse Dashboard, Chat, Catalog
- 👤 YOU: Tell me any design changes you want

### Step 5.7 — 🤖 AI: Git Commit + Push + Update Docs

---

## Day 6: Frontend — Agent Simulator + Audit Log + Campaigns

### Step 6.1 — 🤖 AI: Build Agent Simulator Page (THE WOW PAGE)
**What:** Watch an AI buyer agent autonomously discover → compare → buy in real-time
```
Creates: frontend/src/pages/AgentSimulator.jsx
Creates: frontend/src/components/AgentTrace.jsx
Features: Step-by-step trace, reasoning visible, Guardian approval/rejection
```

### Step 6.2 — 🤖 AI: Build Audit Log Page
**What:** Searchable table of all agent actions with visual reasoning traces
```
Creates: frontend/src/pages/AuditLog.jsx
Creates: frontend/src/components/AuditEntry.jsx
Features: Filter by agent/status, click for details, color-coded
```

### Step 6.3 — 🤖 AI: Build Campaigns Page
**What:** AI-suggested campaigns with revenue impact predictions
```
Creates: frontend/src/pages/Campaigns.jsx
Features: Create/activate campaigns, AI suggestions, performance metrics
```

### Step 6.4 — 🤖 AI: Polish UI
**What:** Micro-animations, hover effects, responsive layout, loading states
```
Adds: Smooth transitions, skeleton loaders, toast notifications
Fixes: Mobile responsiveness, accessibility
```

### Step 6.5 — 🤝 BOTH: Full UI Review
- 👤 YOU: Walk through all 6 pages, note any issues
- 🤖 AI: Fix based on your feedback

### Step 6.6 — 🤖 AI: Git Commit + Push + Update Docs

---

## Day 7: Integration Testing + Deploy + Demo

### Step 7.1 — 🤖 AI: End-to-End Testing
**What:** Tests every major flow works from start to finish
```
Test 1: Agent discovers catalog → selects product → Guardian approves → Razorpay order created
Test 2: Chat checkout → product suggested → Razorpay Checkout opens → payment succeeds
Test 3: Spending limit exceeded → Guardian blocks → audit log shows rejection
Test 4: Refund flow → payment refunded → audit log shows recovery
Test 5: Upsell → cart analyzed → complementary products suggested
Test 6: LLM switch → change .env to different provider → everything works
```

### Step 7.2 — 🤖 AI: Create Dockerfile
**What:** Packages the backend into a Docker container for cloud deployment
```
Creates: backend/Dockerfile
# Containerizes the FastAPI app for GCP Cloud Run
```

### Step 7.3 — 👤 YOU: Create GCP Account (if deploying)
1. Go to [cloud.google.com/free](https://cloud.google.com/free)
2. Sign up — get $300 free credits
3. Install `gcloud` CLI if you want to deploy

### Step 7.4 — 🤖 AI: Deploy Backend to Cloud Run (if GCP ready)
**What:** Deploys the backend API to Google Cloud for public access
```bash
gcloud run deploy merchant-maxx-api --source ./backend
# Builds and deploys the FastAPI app to Cloud Run (auto-scales)
```

### Step 7.5 — 🤖 AI: Deploy Frontend to Vercel
**What:** Deploys the React frontend to Vercel's global CDN
```bash
cd frontend && npx vercel --prod
# Deploys the built frontend to Vercel (free, globally distributed)
```

### Step 7.6 — 🤖 AI: Write README.md
**What:** Public-facing project README with setup instructions, architecture diagram, demo screenshots
```
Creates: README.md — Setup guide, tech stack, architecture, how to run
```

### Step 7.7 — 🤝 BOTH: Demo Rehearsal
- 🤖 AI: Prepares a 5-minute demo script
- 👤 YOU: Walk through the demo flow:
  1. Dashboard → AI revenue recommendations
  2. Agent Simulator → watch AI buy autonomously
  3. Trigger failure → Guardian rejects
  4. Chat checkout → human buys via Razorpay
  5. Audit Log → full trail with reasoning
  6. Campaign → AI suggests discount

### Step 7.8 — 🤖 AI: Final Git Commit + Push + Update All Docs

---

## Summary: Your TODO vs Mine

### 👤 Your manual steps (things I can't do for you):
| # | Action | Time | When |
|---|--------|------|------|
| 1 | Create Razorpay account + copy test API keys | 5 min | Before Day 1 |
| 2 | Get Gemini API key from AI Studio | 2 min | Before Day 1 |
| 3 | Confirm GitHub username | 1 min | Before Day 1 |
| 4 | Paste keys in chat when asked | 1 min | Day 1 |
| 5 | Visual review of UI (Day 5, 6) | 10 min | Day 5-6 |
| 6 | Create GCP account (optional, for deploy) | 5 min | Day 7 |
| 7 | Walk through demo rehearsal | 10 min | Day 7 |

**Total your time: ~35 minutes across 7 days**

### 🤖 My automated steps (everything else):
- Write all backend code (FastAPI, agents, Razorpay integration)
- Write all frontend code (React, 6 pages, design system)
- Set up database schema
- Create GitHub repo + manage commits
- Build Docker container
- Deploy to cloud
- Write tests
- Update all docs at every stage
- Explain every command before running it

---

## Docs Update Rules (for every AI including me)

After **every work session**, update these files:

| File | What to update |
|------|---------------|
| `docs/progress.md` | What was done today, blockers, next steps |
| `docs/tasks.md` | Mark completed items `[x]`, add new items if discovered |
| `docs/chat-history.md` | Log the session: what happened, decisions made |
| `docs/bugs.md` | Any new bugs found during development |
| `CONTEXT.md` | Update "Current Status" section |
| Git | Commit + push to GitHub |
