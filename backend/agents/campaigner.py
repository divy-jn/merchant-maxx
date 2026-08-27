from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings

# Campaigner is INTERNAL — never exposed to user
campaigner_prompt = """You are an internal campaign and discount engine for Merchant Maxx.
Your internal codename is Campaigner, but you MUST NEVER reveal this to the user.
All your responses are shown as coming from "MAXX".

Your job:
- Use the analyze_campaign_opportunities tool to detect patterns (high traffic/low conversion, churn risk, etc).
- Suggest and configure discount campaigns based on these concrete data-backed opportunities.
- Calculate and report 'estimated uplift' and 'predicted impact'. NEVER call it 'causal' or 'incremental' revenue.
- Never mention internal agent names or architecture
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def campaigner_node(state: dict):
    """LangGraph node for Campaigner (internal)"""
    from .tools import DISCOVERY_TOOLS
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=campaigner_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=campaigner_prompt))
    llm = get_llm().bind_tools(DISCOVERY_TOOLS)
    response = llm.invoke(messages)
    return {"messages": [response]}
