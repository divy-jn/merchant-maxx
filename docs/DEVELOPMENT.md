# Development Guide: Merchant MAXX

## Local Setup

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- Docker (optional, for local DB/Redis emulation)

### 2. Environment Variables
Copy `.env.example` to `.env` in both `backend/` and `frontend/` (or root if unified).
Key required variables:
- `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` (Gemini)
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`
- `PINECONE_API_KEY`
- `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
- `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` (for LangSmith)
- `VITE_API_URL` (Frontend only)

## Run Commands

### Backend (FastAPI)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

### Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```

## Build & Deployment Workflow

### Backend
1. Build the Docker container: `docker build -t merchant-maxx-api ./backend`
2. Push to Google Container Registry and deploy to Cloud Run:
   ```bash
   gcloud run deploy merchant-maxx-api --image gcr.io/PROJECT_ID/merchant-maxx-api --platform managed --allow-unauthenticated
   ```

### Frontend
1. Connect the GitHub repository to Vercel for automatic deployments on push.
2. Alternatively, manually build and deploy:
   ```bash
   npm run build
   npx vercel --prod
   ```

## Database Migrations
Database schemas and RLS policies are managed in Supabase. Apply schema updates via the Supabase SQL Editor or CLI.
Always ensure `inventory_decrement_events` and `purchase_intents` are synchronized.

## Tests
- Run full test suite: `pytest backend/tests/`
- Run E2E test scripts: `python backend/scripts/e2e_test.py`

## Troubleshooting
- **Cloud Run Cold Starts**: Free tier scales to 0. The first request may take ~30s. Consider setting `--min-instances=1` if acceptable.
- **CORS Errors**: Verify that `VITE_API_URL` matches the backend and that `CORS_ORIGINS` in the backend `.env` includes the frontend URL.
