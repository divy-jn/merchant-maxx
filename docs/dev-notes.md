# 🛠️ Developer Notes — Merchant Maxx

> Gotchas, tips, environment setup quirks, and things to remember.

---

## Command Reference

Every command you'll see in this project, explained in one line:

### Python / Backend
| Command | What it does |
|---------|-------------|
| `pip install -r requirements.txt` | Installs all Python dependencies listed in requirements.txt |
| `uvicorn main:app --reload` | Starts the FastAPI dev server with auto-reload on code changes |
| `python -m pytest tests/ -v` | Runs all backend tests with verbose output |
| `ruff check .` | Lints Python code for style/error issues |
| `pip install razorpay` | Installs the official Razorpay Python SDK |
| `pip install litellm` | Installs the LLM gateway library (supports 100+ providers) |
| `pip install langgraph` | Installs LangGraph for multi-agent state machine orchestration |

### Node / Frontend
| Command | What it does |
|---------|-------------|
| `npm create vite@latest ./ -- --template react` | Scaffolds a new React project with Vite in current directory |
| `npm install` | Installs all JavaScript dependencies from package.json |
| `npm run dev` | Starts the Vite dev server (usually http://localhost:5173) |
| `npm run build` | Creates production-optimized static files in dist/ folder |

### Docker / Deployment
| Command | What it does |
|---------|-------------|
| `docker build -t agentbazaar-api ./backend` | Builds a Docker image for the backend |
| `gcloud run deploy` | Deploys a container to GCP Cloud Run (serverless) |
| `npx vercel --prod` | Deploys the frontend to Vercel's CDN |

### Git
| Command | What it does |
|---------|-------------|
| `git init` | Initializes a new git repository in current folder |
| `git add .` | Stages all changed files for commit |
| `git commit -m "message"` | Saves staged changes with a description |
| `git push origin main` | Pushes local commits to GitHub |

---

## Razorpay Test Mode Gotchas

1. **Test card number:** `4111 1111 1111 1111` (any expiry, any CVV)
2. **Test UPI ID:** `success@razorpay` (for successful UPI payments)
3. **Amounts are in paise:** ₹500 = `50000` paise
4. **Orders are REQUIRED:** Payments without `order_id` are auto-refunded by Razorpay
5. **Webhooks in test mode:** Limited events: `payout.queued`, `payout.initiated`, `payout.processed`, `payout.reversed`, `transaction.created`
6. **API key prefix:** Test keys always start with `rzp_test_`

## Environment Setup Reminders

1. Always activate Python venv before running backend
2. Frontend runs on port 5173, backend on port 8000
3. CORS is configured to allow `http://localhost:5173` in development
4. Never commit `.env` — only `.env.example`

---

*Last updated: 2026-08-24*
