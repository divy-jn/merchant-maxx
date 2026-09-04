# Merchant Maxx - AI-Native E-commerce Platform (UNDER DEVELOPMENT)

> **Project status — Under Development**
>
> Merchant Maxx is under active development. The core application source is maintained in `backend/` and `frontend/`, with supporting documentation in `docs/`.
>
> **Current state:**
> - The application is deployed through the existing backend/frontend deployment setup.
> - The restored development history contains **108 commits** with original author/committer metadata and timestamps preserved through the security rewrite.
> - Previously exposed credentials were scrubbed from reachable Git history; real credentials must remain in environment/secret-manager configuration and must not be committed.
> - The latest local backend validation recorded **212 passing tests**.
> - Development-only artifacts have been moved into `underConstruction/` so the repository root stays focused on the application and required project files.

Merchant Maxx is a highly resilient AI e-commerce platform built on a multi-agent LangGraph architecture. It allows users to shop interactively through conversational AI while maintaining strict, deterministic transaction guarantees.

## Key Features

1. **Conversational Shopping**: Chat with an AI assistant to discover products. If a request is broad, the AI asks refinement questions rather than dumping the whole catalog. If no exact product exists, it suggests alternatives instead of hallucinating.
2. **Product Recommendations**: Context-aware product recommendations limit choices to the best 2-3 matching products based on vector search and conversation state.
3. **Cart and Checkout**: Add products to your cart via chat. When you explicitly confirm your cart, the system locks the basket deterministically and transitions to payment without looping confirmation prompts.
4. **Razorpay Integration**: Secure payments powered by Razorpay. Once confirmed, a customer-safe payment prompt is provided in chat without exposing internal Razorpay IDs.
5. **AI Stack**: Powered by a LangGraph multi-agent system.

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

### Testing
To run the automated tests locally, you must set the `APP_ENV` environment variable to `test`.
```bash
$env:APP_ENV="test"
python -m pytest backend/tests/ -v
```

### Deploying
The backend is continuously deployed to Google Cloud Run:
```bash
gcloud run deploy merchant-maxx-api --source backend --region us-central1 --allow-unauthenticated --env-vars-file env_deploy_new.yaml
```

## Known Limitations
- The project is still under active development.
- The conversational flow for certain edge cases is being continually refined.
