# Merchant Maxx - AI-Native E-commerce Platform

Merchant Maxx is a production-grade, highly resilient AI e-commerce platform built on a multi-agent LangGraph architecture. It allows users to shop interactively through conversational AI while maintaining strict, deterministic transaction guarantees.

## Architecture

* **Backend**: FastAPI & Python 3.11+
* **AI Orchestration**: LangGraph (Multi-Agent System) & LangChain
* **LLM Gateway**: OpenAI OR Gemini (selectable via LLM_PROVIDER env var; one active provider at a time, no automatic fallback)
* **Database & Auth**: Supabase (PostgreSQL) - Authoritative for all commerce state
* **Payments**: Razorpay (backend-controlled deterministic flow)
* **Observability**: LangSmith
* **Hosting**: Google Cloud Run (Backend) & Vercel (Frontend)

### Multi-Agent System (LangGraph)
The AI backend uses a highly concurrent graph architecture:
* **Scout**: Handles product search, inventory checking, and adding items to the basket.
* **Booster**: Runs concurrently with Scout to dynamically cross-sell or up-sell related products.
* **Merger**: Synchronizes the concurrent outputs of Scout and Booster, ensuring exactly-once execution of tool calls and deduplicating AI responses.
* **Closer**: Handles the critical checkout flow, requiring authoritative server-side confirmation before securely initiating Razorpay orders.
* **Campaigner**: Proactive engagement agent (optional).

## Production Robustness Guarantees

Over a rigorous hardening phase, the following guarantees have been implemented and verified:

### 1. Zero "Ghost Orders" Guarantee
We implemented a multi-layered, idempotent transaction recovery system to ensure customers are never charged without a corresponding local order:
* **Strict Atomic Locks**: Database states (`purchase_state`) are transitioned using strict atomic conditionals to prevent race conditions.
* **Pre-Flight Persistence**: Razorpay Order IDs are persisted to the Supabase `orders` table *before* they are returned to the frontend.
* **Automated Webhook Recovery**: If a Razorpay payment succeeds but the local frontend fails to complete the loop, the `payment.captured` webhook will autonomously reconstruct the basket and provision the missing local order.

### 2. Dual Provider Support (No Fallback)
The AI pipeline supports selecting either OpenAI (defaulting to gpt-4o-mini) or Gemini via environment variables. There is no LiteLLM, Nemotron, or automatic model/key fallback runtime. Exactly one provider is active at any time.

* **Vector Database**: Pinecone
* **Relational Database**: Supabase (PostgreSQL with Row Level Security)
* **Payment Gateway**: Razorpay Test Mode
* **Testing**: Pytest + custom local memory fallback mocks

### 3. Fortified Database Security (RLS)
The database is locked down with strict Row Level Security (RLS) policies:
* Users can only read and mutate their own carts and orders.
* Webhooks use secure `SERVICE_ROLE` overrides to safely fulfill orders without exposing permissions to the client.

### 4. Deterministic AI Guardrails
* The LLM cannot hallucinate transaction amounts, basket contents, or Razorpay IDs.
* Basket totals are recalculated authoritative server-side by checking real-time database inventory and prices before allowing Razorpay to generate a payment link.
* Frontend deterministic action endpoints (`/chat/action`) handle commerce transitions, completely isolating payment validation from natural language generation.

## Development & Deployment

### Environment Variables
Copy `.env.example` to `.env` and configure your API keys.

### Running Locally
```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
python main.py

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

### Deploying
The backend is continuously deployed to Google Cloud Run:
```bash
gcloud run deploy merchant-maxx-api --source backend --region us-central1 --allow-unauthenticated --env-vars-file env_deploy_new.yaml
```
