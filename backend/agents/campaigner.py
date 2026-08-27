from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import CAMPAIGNER_TOOLS

campaigner_prompt = """You are MAXX's internal merchant growth analyst.
Use analyze_campaign_opportunities to identify evidence-backed opportunities.
Report estimated uplift/predicted impact only; never call it causal or incremental revenue.
Never reveal internal agent names or architecture to customers.
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def campaigner_node(state: dict):
    messages = list(state.get("messages", []))
    response = get_llm().bind_tools(CAMPAIGNER_TOOLS).invoke([SystemMessage(content=campaigner_prompt)] + messages)
    return {"messages": [response]}
