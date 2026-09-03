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
# ❓ Q&A Log — Merchant Maxx

> Every question asked during planning/development and its resolved answer. Keeps decision context alive.

---

## Q1: Is ACP the same as Google A2A?

**Asked:** 2026-08-24 | **Status:** ✅ Resolved

**Short answer:** No — they are **different protocols that work together** at different layers.

| | ACP (Agentic Commerce Protocol) | A2A (Agent-to-Agent Protocol) |
|---|---|---|
| **Created by** | OpenAI + Stripe | Google |
| **Purpose** | Commerce-specific: catalog discovery, cart, checkout, payments | Agent coordination: how agents find, talk to, and delegate to each other |
| **Layer** | Application/Commerce layer (the "what") | Communication/Orchestration layer (the "how") |
| **Relationship** | Runs **on top of** A2A for commerce tasks | Foundation layer — agent discovery, handshake, task delegation |

**How they fit together (Protocol Stack):**
```
┌─────────────────────────┐
│  ACP / UCP              │  ← Commerce semantics (buy, cart, checkout)
├─────────────────────────┤
│  A2A                    │  ← Agent-to-agent communication & discovery
├─────────────────────────┤
│  MCP                    │  ← Tool/data connectivity (local tools, DBs, APIs)
└─────────────────────────┘
```

**Our approach:** We use an **ACP-inspired** protocol (agent-readable catalog + checkout endpoints) for the commerce layer, with our own LangGraph orchestrator handling agent coordination internally. We don't need full A2A for a hackathon demo, but our architecture is compatible with it.

---

## Q2: Is LiteLLM free to use?

**Asked:** 2026-08-24 | **Status:** ✅ Resolved

**Yes — the core is 100% free and open-source (MIT license).**

| Tier | Cost | What you get |
|------|------|-------------|
| **Open Source (self-hosted)** | **$0** | Full proxy + SDK, 100+ LLM providers, virtual keys, spend tracking, load balancing |
| **Enterprise** | ~$250+/month | SSO, SCIM, advanced RBAC, dedicated support |

**Important:** LiteLLM is a **proxy/gateway**, not an LLM provider. You still pay the underlying model provider (Gemini, OpenAI, etc.) for tokens consumed. But Gemini Flash free tier (15 RPM) is enough for our hackathon.

**For our project:** We use LiteLLM as a **Python library** (`pip install litellm`) — not even the proxy server. Zero infrastructure cost. Just call `litellm.completion()` with any provider.

---

## Q3: Can I get a free domain?

**Asked:** 2026-08-24 | **Status:** ✅ Resolved

**Best free options:**

| Option | Domain | How | Duration |
|--------|--------|-----|----------|
| **GitHub Pages** | `username.github.io` | Free with any GitHub account | Forever |
| **Vercel** | `project.vercel.app` | Free deployment subdomain | Forever |
| **Render** | `project.onrender.com` | Free deployment subdomain | Forever |
| **Railway** | `project.up.railway.app` | Free deployment subdomain | Forever |
| **GitHub Student Pack** | `.me`, `.tech`, `.live`, `.dev` | Verify student status at [education.github.com](https://education.github.com) | 1 year free |
| **Namecheap (via Student Pack)** | `.me` + free SSL | Part of GitHub Student Pack | 1 year free |

**Recommendation for hackathon:** Use **Render/Railway free subdomain** (e.g., `agentbazaar.onrender.com`) — zero cost, instant deploy. If you want a custom domain for impressiveness, get a `.tech` from GitHub Student Pack.

---

## Q4: GCP vs AWS for deployment?

**Asked:** 2026-08-24 | **Status:** ✅ Resolved

| | GCP | AWS |
|---|---|---|
| **Free credits** | **$300** for 90 days | **$100-200** for 6 months |
| **Best for FastAPI** | **Cloud Run** (serverless, scale-to-zero, auto-scales) | **Lambda + Mangum** (serverless) or **EC2** (VM) |
| **Always Free** | Cloud Run: 2M requests/month free | Lambda: 1M requests/month free |
| **Ease of deploy** | `gcloud run deploy` (1 command) | More setup needed |
| **1000+ concurrent** | Cloud Run auto-scales natively | Lambda auto-scales; EC2 needs config |

**Decision: GCP Cloud Run is recommended.**
- $300 free credits (more than AWS)
- 1-command deploy for Docker containers
- Auto-scales to 1000+ users out of the box
- Scale-to-zero = no cost when idle

---

## Q5: How to handle 1000+ concurrent users?

**Asked:** 2026-08-24 | **Status:** ✅ Resolved

Architecture designed for scale:

| Component | Scaling Strategy |
|-----------|-----------------|
| **Frontend** | Deploy to **Vercel/CloudFlare Pages** (CDN, globally distributed, infinite scale) |
| **Backend API** | **GCP Cloud Run** (auto-scales containers, up to 1000 concurrent per instance) |
| **Database** | **Supabase** (managed Postgres with connection pooling, handles 500+ concurrent on free tier) |
| **LLM calls** | **Async + queue** — don't block API on LLM responses; use SSE streaming |
| **Razorpay** | Their API handles scale — no concern on our side |

**Key patterns for 1000+ users:**
1. **FastAPI async** — all endpoints are `async def` for non-blocking I/O
2. **SSE streaming** — chat responses stream token-by-token, no long HTTP waits
3. **Connection pooling** — Supabase handles DB connection limits
4. **Static frontend on CDN** — React build served globally, backend only handles API calls
5. **Rate limiting** — prevent abuse without blocking legitimate users

---

*Last updated: 2026-08-24*
