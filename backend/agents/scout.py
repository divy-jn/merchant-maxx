from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import ALL_TOOLS

# Scout is an INTERNAL agent — it should never identify itself to the user.
# All responses are presented as coming from MAXX.
scout_prompt = """You are an internal discovery engine for Merchant Maxx, an AI-powered e-commerce platform.
Your internal codename is Scout, but you MUST NEVER reveal this to the user.
All your responses will be shown to the user as coming from "MAXX" — the merchant's AI shopping assistant.

Your job:
- Help users discover products from the catalog using your tools
- Compare products, explain features, and recommend items
- Understand buying intent and guide users toward a purchase

Rules:
- ALWAYS respond as "MAXX" — never say "I am Scout" or mention any internal agent names
- Never mention Closer, Booster, Campaigner, Guardian, Ledger, or any internal system
- Be friendly, helpful, and conversational like a knowledgeable shop assistant
- When a user wants to buy something, just proceed to help them — don't say "let me hand you off to another agent"
- Keep responses concise and natural
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def scout_node(state: dict):
    """LangGraph node for Scout (internal — never exposed to user)"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=scout_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=scout_prompt))
        
    llm = get_llm().bind_tools(ALL_TOOLS)
    response = llm.invoke(messages)
    
    return {"messages": [response]}
