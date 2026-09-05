# Architecture: Merchant MAXX

## System Architecture
Merchant MAXX is a multi-agent AI commerce platform built on a decoupled, scalable architecture designed for high-concurrency environments.

### Core Components
- **Frontend (Vercel)**: React + Vite application hosted on a global CDN. Premium dark-mode glassmorphism theme. Zero backend load for static page delivery.
- **Backend (GCP Cloud Run)**: FastAPI Python application running in a Docker container. Auto-scales from 0 to N instances.
- **Database (Supabase)**: Managed PostgreSQL handling users, conversations, audit logs, purchase intents, and inventory management with connection pooling.
- **AI Orchestration**: LangGraph StateGraph (MAXX) managing specialized sub-agents.
- **Search (Pinecone + Gemini)**: Vector search for catalog products using Gemini embeddings.
- **Caching & Rate Limiting (Upstash Redis)**: Handles rate limiting (100 req/min/IP) and high-speed data caching.
- **Payments (Razorpay)**: Razorpay test mode integrated via official Python SDK for items, orders, payment links, and webhook-based fulfillment.
- **Observability (LangSmith)**: Traces agent reasoning, LLM inputs/outputs, and latency.

## Major Responsibilities
- **MAXX Orchestrator**: The only customer-facing agent. Routes intents internally, maintaining a cohesive persona.
- **Scout Agent**: Handles product discovery, semantic search (`search_catalog`), intent extraction, and cart mutations.
- **Closer Agent**: Executes checkout flows, creates Razorpay orders (`create_razorpay_order`), and generates payment links.
- **Booster & Campaigner Agents**: Provide data-driven upsell recommendations and targeted discounts based on Supabase `product_affinity` logic.
- **Guardian Agent**: Constitutional AI safety gate that strictly validates all money actions deterministically before allowing execution.
- **Ledger Agent**: Immutable audit logger ensuring all AI reasoning and transactions are securely logged to Supabase.

## Deployment Topology
- **Vercel** (`agentbazaar.vercel.app`): Serves the React frontend globally.
- **GCP Cloud Run** (`merchant-maxx-api-*.run.app`): Hosts the FastAPI backend.
- **Supabase**: Primary persistent data store (PostgreSQL) and Auth.
- **Upstash Redis**: Serverless Redis for distributed rate-limiting.
- **Pinecone**: Serverless vector database.

## Important Data Flows
1. **User Request**: User sends a chat message via Vercel CDN.
2. **Backend API**: Cloud Run receives the request, loads session history and purchase intent from Supabase.
3. **LangGraph Execution**: MAXX routes to Scout/Closer based on intent.
4. **Tool Execution**: Scout searches Pinecone/Razorpay catalog; Closer may trigger Razorpay Order creation.
5. **Safety Gate**: Guardian validates any proposed financial transaction against strict rules (e.g., `RULE_06` user_confirmed).
6. **Payment Flow**: Razorpay handles payment; webhooks notify Cloud Run to fulfill order and update Supabase (atomic inventory decrement).
