from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings

campaigner_prompt = """You are Campaigner, the Campaign & Discount Engine for Merchant Maxx.
Your goal is to suggest and configure discount campaigns based on merchant inventory and sales goals.
You can analyze which products might need a discount to move inventory and calculate predicted revenue impact.
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def campaigner_node(state: dict):
    """LangGraph node for Campaigner"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=campaigner_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=campaigner_prompt))
        
    llm = get_llm()
    response = llm.invoke(messages)
    
    return {"messages": [response]}
