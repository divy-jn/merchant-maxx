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
    from langchain_core.messages import merge_message_runs
    messages_to_invoke = merge_message_runs([SystemMessage(content=campaigner_prompt)] + messages)
    response = get_llm().bind_tools(CAMPAIGNER_TOOLS).invoke(messages_to_invoke)
    if isinstance(getattr(response, "content", None), list):
        response.content = "".join(str(b.get("text", "")) for b in response.content if isinstance(b, dict))
    return {"messages": [response]}
