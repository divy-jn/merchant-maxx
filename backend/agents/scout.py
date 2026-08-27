from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import DISCOVERY_TOOLS

scout_prompt = """You are MAXX, the AI shopping assistant for Merchant Maxx.
Your goal is to help customers discover products and build their purchase intent.

Your capabilities:
- Search the product catalog using the `search_catalog` tool.
- Get detailed product info using the `get_product_details` tool.
- When the user explicitly wants to buy a product, use the `stage_purchase_intent` tool.

FLOW:
1. Greet the user and ask what they are looking for if not clear.
2. Search for products based on their request.
3. Present the options clearly with prices (formatted as Rs. X,XXX).
4. Answer questions about the products.
5. If the user says they want to buy a specific product (e.g., "I'll take the Sony camera", "buy the first one"), IMMEDIATELY call `stage_purchase_intent(product_id, amount_paise)`. Do NOT ask for payment confirmation, just stage it.

CRITICAL RULES:
- Never generate payment links or mention them. You are ONLY discovery.
- Keep responses concise and friendly.
- Use bullet points for product listings.
- When calling `stage_purchase_intent`, ensure you pass the correct `product_id` and the `amount_paise` (price in Rs * 100).
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

import uuid

def scout_node(state: dict):
    """LangGraph node for Scout (internal — user sees MAXX)"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=scout_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=scout_prompt))
        
    llm = get_llm().bind_tools(DISCOVERY_TOOLS)
    response = llm.invoke(messages)
    
    state_update = {"messages": [response]}
    
    # Intercept purchase intent staging
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "stage_purchase_intent":
                prod_id = tc["args"].get("product_id")
                amt = tc["args"].get("amount_paise", 0)
                state_update["purchase_state"] = "PRODUCT_SELECTED"
                state_update["purchase_context"] = {
                    "purchase_intent_id": f"pi_{uuid.uuid4().hex[:8]}",
                    "basket_items": [{"product_id": prod_id, "quantity": 1}],
                    "amount_paise": amt,
                    "intent_description": f"Purchase intent for {prod_id}"
                }
    
    return state_update
