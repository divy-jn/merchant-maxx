# 💬 Conversation & Chat History — Merchant Maxx

> Summary of all key conversations during project development. Keeps context alive across sessions.

---

## Session 1 — Initial Planning (2026-08-24, 01:48 - 02:09 IST)

### What happened
- User requested to build **Track 01: AI Growth & Agentic Commerce** for a hackathon
- Asked all scoping questions (10 questions via interactive modal)
- Researched Razorpay APIs, ACP protocol, NPCI UAP

### Key user answers
- **Direction:** All directions — conversational checkout + agent-readable catalog + upsell + campaign orchestrator
- **Primary user:** Two-sided system (merchant dashboard + AI buyer agent)
- **Tech stack:** Python FastAPI + React/HTML frontend
- **LLM:** Gemini or open-source, switchable via .env
- **Database:** PostgreSQL via Supabase
- **Team:** Solo project
- **Timeline:** 1 week
- **Razorpay experience:** Never used — needs full guidance
- **Ambition:** Use best/new/free technologies, multi-agent with ACP

### Outputs
- Created `implementation_plan.md` v1

---

## Session 2 — Research Deepening (2026-08-24, 02:04 - 02:09 IST)

### What happened
- User shared additional resources:
  - [razorpay/ai-playbook](https://github.com/razorpay/ai-playbook) — Razorpay's internal AI builder program
  - [razorpay GitHub org](https://github.com/razorpay) — found official `razorpay-python` SDK
  - [Razorpay docs](https://razorpay.com/docs/#home-payments) — Standard Checkout flow details

### Key findings
- **AI Playbook** has multi-agent orchestration patterns (B.5), fintech guardrails (G.22-G.28), tool design (B.6)
- **razorpay-python SDK** exists — use instead of raw HTTP
- **Standard Checkout** requires `order_id` for every payment (critical!)
- **Payment flow:** Create Order → Checkout Modal → Verify Signature → Capture

### Outputs
- Updated `implementation_plan.md` v2 with Razorpay insights

---

## Session 3 — Clarifications & Docs Setup (2026-08-24, 11:07 - 11:20 IST)

### User questions answered
1. **ACP vs A2A:** Different protocols, complementary layers (ACP = commerce, A2A = agent communication)
2. **LiteLLM:** 100% free, MIT license, open-source Python library
3. **Free domain:** Vercel/Render subdomains free forever; GitHub Student Pack for `.tech`/`.me`
4. **GCP vs AWS:** GCP Cloud Run recommended ($300 credits, auto-scales, 1-command deploy)
5. **1000+ concurrent users:** Vercel CDN (frontend) + Cloud Run auto-scaling (backend) + Supabase pooling

### User requests
- Create `docs/` folder for all project tracking documents
- Always explain commands with a one-liner before executing
- Copy Antigravity internal files to docs/ at each stage

### Outputs
- Created `docs/` folder with 8 documents: README, tasks, decisions, qna, bugs, progress, deployment, dev-notes
- Updated `implementation_plan.md` v3 with resolved questions
- Copied plan to `docs/plan.md`

---

## Session 4 — LLM-Portable Docs + Execution Plan (2026-08-24, 11:27 - 11:30 IST)

### User requests
- Design docs so ANY other LLM can understand the full project instantly
- Every command must have a 1-line explanation
- Keep updating docs at each stage
- Set up GitHub repo for Divy Jain (divyjn28@gmail.com)
- Create a step-by-step plan showing what USER does vs what AI does

### What was created
1. **`CONTEXT.md`** (project root) — Single file any LLM reads first to understand everything
   - Project overview, tech stack, architecture, directory structure
   - Current status, how to run, key conventions
   - "For Other LLMs" section with reading order
2. **Updated `implementation_plan.md`** — Now split into 👤 YOU / 🤖 AI / 🤝 BOTH steps
   - Every command has a 1-line explanation
   - Summary table: user needs ~35 min total across 7 days
3. **GitHub repo setup** — Pending user confirmation of GitHub username

### Key decisions
- `CONTEXT.md` at project root = universal entry point for any AI
- All docs updated at every stage (automated via convention)
- Git commit after each logical chunk of work

### Outputs
- `CONTEXT.md` created at project root
- `implementation_plan.md` rewritten as step-by-step execution plan
- Synced to `docs/plan.md`

---

## Antigravity Internal Files Reference

The following Antigravity-generated files have been mirrored to `docs/`:

| Antigravity Path | Copied To | When |
|---|---|---|
| `brain/<conv-id>/implementation_plan.md` | `docs/plan.md` | Session 3 (2026-08-24) |
| `brain/<conv-id>/implementation_plan.md` | `docs/plan.md` | Session 4 (2026-08-24) — updated with execution steps |

> **Policy:** At each development stage, any new Antigravity artifacts (plans, walkthroughs, task lists) will be copied to `docs/` for persistent project memory.

---

*Last updated: 2026-08-24*
