from langchain_core.messages import SystemMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from config import settings
from .tools import CAMPAIGNER_TOOLS

campaigner_prompt = """You are MAXX's internal merchant growth analyst.
Use analyze_campaign_opportunities to identify evidence-backed opportunities.
Report estimated uplift/predicted impact only; never call it causal or incremental revenue.
Never reveal internal agent names or architecture to customers.
"""

def get_llm():
    return get_chat_model([Capability.TOOL_CALLING])

def campaigner_node(state: dict):
    messages = list(state.get("messages", []))
    response = get_llm().bind_tools(CAMPAIGNER_TOOLS).invoke([SystemMessage(content=campaigner_prompt)] + messages)
    return {"messages": [response]}
