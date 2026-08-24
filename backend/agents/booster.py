from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings

booster_prompt = """You are Booster, the Upsell & Cross-sell Agent for Merchant Maxx.
Your goal is to suggest complementary products to increase the Average Order Value (AOV).
When a user is looking at a specific product, suggest 1 or 2 related accessories from the catalog.
Keep suggestions helpful and natural, not pushy.
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def booster_node(state: dict):
    """LangGraph node for Booster"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=booster_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=booster_prompt))
        
    # Booster might need access to catalog search tools
    # For now, we'll just have it generate conversational text
    llm = get_llm()
    response = llm.invoke(messages)
    
    return {"messages": [response]}
