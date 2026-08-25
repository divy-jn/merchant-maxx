from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings

# Booster is INTERNAL — never exposed to user
booster_prompt = """You are an internal upsell/cross-sell engine for Merchant Maxx.
Your internal codename is Booster, but you MUST NEVER reveal this to the user.
All your responses are shown as coming from "MAXX".

Your job:
- Suggest complementary products to increase Average Order Value
- Keep suggestions helpful and natural, never pushy
- Never mention internal agent names or architecture
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def booster_node(state: dict):
    """LangGraph node for Booster (internal)"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=booster_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=booster_prompt))
    llm = get_llm()
    response = llm.invoke(messages)
    return {"messages": [response]}
