# Merchant Maxx - AI-Native E-commerce Platform

Merchant Maxx is a production-grade, highly resilient AI e-commerce platform built on a multi-agent LangGraph architecture. It allows users to shop interactively through conversational AI while maintaining strict, deterministic transaction guarantees.

## Architecture

* **Backend**: FastAPI & Python 3.11+
* **AI Orchestration**: LangGraph (Multi-Agent System) & LangChain
* **LLM Gateway**: Direct Gemini Integration
* **Database & Auth**: Supabase (PostgreSQL)
* **Payments**: Razorpay
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

### 2. Autonomous Multi-Model Fallback
The AI pipeline is protected against vendor outages and rate limits:
* **LLM Integration**: Direct Gemini integration
* **Multi-Agent Orchestration**: LangGraph (Scout, Booster, Merger, Closer, Campaigner)
* **Vector Database**: Pinecone
* **Relational Database**: Supabase (PostgreSQL with Row Level Security)
* **Payment Gateway**: Razorpay Test Mode
* **Testing**: Pytest + custom local memory fallback mocks
* **Zero-Timeout Failover**: By intercepting and normalizing HTTP 429 Quota Exhaustion errors, the backend triggers fallback instantly without sleeping, preventing Cloud Run 504 timeouts.

### 3. Fortified Database Security (RLS)
The database is locked down with strict Row Level Security (RLS) policies:
* Users can only read and mutate their own carts and orders.
* Webhooks use secure `SERVICE_ROLE` overrides to safely fulfill orders without exposing permissions to the client.

### 4. Deterministic AI Guardrails
* The LLM cannot hallucinate transaction amounts, basket contents, or Razorpay IDs.
* Basket totals are recalculated authoritative server-side by checking real-time database inventory and prices before allowing Razorpay to generate a payment link.
* AIMessage list-content transformation bugs deep within the LangChain/LiteLLM bridge are explicitly flattened to guarantee stability.

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
