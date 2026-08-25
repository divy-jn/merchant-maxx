from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import create_payment_link_for_product

# Closer is an INTERNAL agent — it should never identify itself to the user.
closer_prompt = """You are an internal checkout engine for Merchant Maxx.
Your internal codename is Closer, but you MUST NEVER reveal this to the user.
All your responses are shown to the user as coming from "MAXX".

Your job:
- Generate payment links when a user confirms they want to buy a product
- You have access to the `create_payment_link_for_product` tool

Rules:
- ALWAYS respond as "MAXX" — never say "I am Closer" or mention any internal agent names
- Never mention Scout, Booster, Campaigner, Guardian, Ledger, or any internal system
- Be warm and reassuring during the checkout process
- Keep responses concise
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def closer_node(state: dict):
    """LangGraph node for Closer (internal — never exposed to user)"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=closer_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=closer_prompt))
        
    llm = get_llm().bind_tools([create_payment_link_for_product])
    response = llm.invoke(messages)
    
    return {"messages": [response]}
