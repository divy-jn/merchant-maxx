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
# 🚀 Deployment Guide — Merchant Maxx

> Infrastructure decisions, deployment strategy, scaling, and domain setup.

---

## Architecture for 1000+ Concurrent Users

```
┌──────────────────────────────────────────────────────────┐
│                    USERS (1000+)                          │
└──────────────────────┬───────────────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │   Vercel CDN (Frontend)  │  ← React build, globally distributed
          │   agentbazaar.vercel.app │     Infinite scale, zero config
          └────────────┬────────────┘
                       │ API calls only
          ┌────────────▼────────────┐
          │  GCP Cloud Run (Backend) │  ← FastAPI in Docker container
          │  Auto-scales 0→N        │     $300 free credits, 2M req/mo free
          │  Max 1000 concurrent/    │
          │  instance, multi-instance│
          └────────────┬────────────┘
                       │
          ┌────────────▼────────────┐
          │  Supabase (Database)     │  ← Managed PostgreSQL
          │  Connection pooling      │     Free tier: 500MB, 50k rows
          │  Real-time subscriptions │
          └─────────────────────────┘
```

---

## Deployment Steps

### 1. Frontend → Vercel (Free)

```bash
# Connect GitHub repo → Vercel auto-deploys
# OR manual deploy:
cd frontend
npm run build
npx vercel --prod
```

- **URL:** `agentbazaar.vercel.app` (free subdomain)
- **Cost:** $0 (free tier: 100GB bandwidth/month)
- **Scale:** CDN globally distributed, handles any traffic

### 2. Backend → GCP Cloud Run

```bash
# Build Docker image
docker build -t agentbazaar-api ./backend

# Push to Google Container Registry
gcloud auth configure-docker
docker tag agentbazaar-api gcr.io/PROJECT_ID/agentbazaar-api
docker push gcr.io/PROJECT_ID/agentbazaar-api

# Deploy to Cloud Run (auto-scales to 1000+ concurrent)
gcloud run deploy agentbazaar-api \
  --image gcr.io/PROJECT_ID/agentbazaar-api \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars "LLM_PROVIDER=gemini,LLM_MODEL=gemini-2.0-flash" \
  --memory 512Mi \
  --max-instances 10 \
  --concurrency 80
```

- **URL:** `agentbazaar-api-xxxxx.a.run.app`
- **Cost:** $300 free credits → ~3+ months of moderate usage
- **Scale:** Auto-scales 0→10 instances, 80 concurrent per instance = 800 concurrent max

### 3. Database → Supabase (Free Tier)

- Already configured via MCP tools
- Connection pooling enabled (handles 60 concurrent connections)
- For 1000+ users: Supabase Pro ($25/month) if free tier isn't enough

---

## Free Domain Options

| Option | Domain | Cost | Best For |
|--------|--------|------|----------|
| **Vercel subdomain** | `agentbazaar.vercel.app` | Free forever | Quick demo |
| **Cloud Run subdomain** | `agentbazaar-xxx.a.run.app` | Free forever | API endpoint |
| **GitHub Student Pack** | `agentbazaar.tech` | Free 1 year | Professional look |
| **Namecheap .me** | `agentbazaar.me` | Free 1 year (Student Pack) | Portfolio |
| **Name.com .dev** | `agentbazaar.dev` | Free 1 year (Student Pack) | Developer cred |

**To get GitHub Student Pack domains:**
1. Go to [education.github.com](https://education.github.com)
2. Verify student status (school email or ID)
3. Access "Domains" section
4. Claim `.tech` from Get.tech or `.me` from Namecheap
5. ⚠️ **Disable auto-renewal immediately** to avoid charges after year 1

---

## GCP Setup Checklist

- [ ] Create GCP account at [cloud.google.com/free](https://cloud.google.com/free)
- [ ] Claim $300 free credits (requires credit card for verification, NOT charged)
- [ ] Install `gcloud` CLI
- [ ] Create project: `gcloud projects create agentbazaar`
- [ ] Enable Cloud Run API: `gcloud services enable run.googleapis.com`
- [ ] Enable Container Registry: `gcloud services enable containerregistry.googleapis.com`
- [ ] Set up billing alerts: `gcloud billing budgets create` (set at $10 warning)

---

## Scaling Considerations

| Concern | Solution |
|---------|----------|
| LLM rate limits | Queue system + retry with exponential backoff |
| DB connections | Supabase connection pooling (PgBouncer) |
| Cold starts | Cloud Run min instances = 1 (keeps 1 warm) |
| Static assets | Vercel CDN handles all frontend traffic |
| Razorpay rate limits | SDK has built-in retry: `client.enable_retry(True)` |
| WebSocket/SSE | Cloud Run supports SSE for streaming responses |

---

*Last updated: 2026-08-24*
