from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import ALL_TOOLS

scout_prompt = """You are Scout, the Discovery & Intent Agent for Merchant Maxx.
Your job is to help users discover products, compare them, and understand their buying intent.
You have access to the merchant's catalog via tools.
Always be helpful, conversational, and focused on finding the right product for the user.
If a user wants to buy a product, pass them to the Closer agent or provide the payment link if you generate it.
"""

def get_llm():
    # In a real app we'd use litellm here for abstraction, but LangChain Google GenAI works natively
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def scout_node(state: dict):
    """LangGraph node for Scout"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=scout_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=scout_prompt))
        
    llm = get_llm().bind_tools(ALL_TOOLS)
    response = llm.invoke(messages)
    
    return {"messages": [response]}
