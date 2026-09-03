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
# 📁 Merchant Maxx — Project Documentation Hub

> **Purpose:** This folder is the single source of truth for all project development tracking — plans, tasks, audit logs, bugs, Q&A, decisions, and progress history. Updated continuously as the project evolves.

---

## 📂 Folder Structure

```
docs/
├── README.md                  # ← You are here (index)
├── plan.md                    # Master implementation plan (synced from Antigravity)
├── tasks.md                   # Task tracker (TODO / In Progress / Done)
├── decisions.md               # Architecture & design decisions log
├── qna.md                     # Questions asked, answers received
├── bugs.md                    # Bug tracker
├── progress.md                # Daily progress journal
├── deployment.md              # Deployment guide & infra decisions
├── dev-notes.md               # Developer notes, tips, gotchas
└── chat-history.md            # Conversation log across sessions
```

## 🔗 Quick Links

| Document | Purpose |
|----------|---------|
| [plan.md](plan.md) | Full implementation plan with architecture, tech stack, timelines |
| [tasks.md](tasks.md) | What's TODO, in progress, and done |
| [decisions.md](decisions.md) | Why we chose X over Y — every major design decision |
| [qna.md](qna.md) | All clarification questions and answers from planning |
| [bugs.md](bugs.md) | Known bugs, reproduction steps, status |
| [progress.md](progress.md) | Day-by-day development journal |
| [deployment.md](deployment.md) | GCP/AWS deployment strategy, domain, scaling |
| [dev-notes.md](dev-notes.md) | Gotchas, tips, environment setup notes |
| [chat-history.md](chat-history.md) | Full conversation log + user decisions across sessions |

## Quick Status
**Phase**: COMPLETE & DEPLOYED TO PRODUCTION 🚀
**Last updated**: 2026-09-02
**Key Achievements**:
- Multi-agent LangGraph architecture is complete.
- E2E Ghost Order Prevention & Atomic Locks are fully functional.
- Zero-downtime multi-model fallback is active.
- Supabase RLS policies secure all data.
- System deployed on Google Cloud Run and Vercel.

## 📋 Antigravity Sync Policy

> All Antigravity internal artifacts (plans, walkthroughs, task lists) are **automatically copied** to this `docs/` folder at each development stage. This ensures the project has a self-contained memory track independent of the AI tool.

---

*Last updated: 2026-09-02*
