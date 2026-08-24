from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import create_payment_link_for_product

closer_prompt = """You are Closer, the Checkout & Purchase Execution Agent for Merchant Maxx.
Your job is strictly to execute purchases by generating payment links for products when a user shows clear intent to buy.
You have access to the `create_payment_link_for_product` tool.
Once a user confirms they want a product (and you have the product ID), generate the link.
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def closer_node(state: dict):
    """LangGraph node for Closer"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=closer_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=closer_prompt))
        
    # Closer only has access to the payment link tool
    llm = get_llm().bind_tools([create_payment_link_for_product])
    response = llm.invoke(messages)
    
    return {"messages": [response]}
