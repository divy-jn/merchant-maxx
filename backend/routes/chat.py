from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from agents.maxx import maxx_app
from langchain_core.messages import HumanMessage, AIMessage
from routes.auth import get_user_from_session

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory chat history per session
chat_histories: Dict[str, List] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "guest"

@router.post("/")
async def chat_with_maxx(req: ChatRequest):
    try:
        # Get or create chat history for this session
        if req.session_id not in chat_histories:
            chat_histories[req.session_id] = []
        
        history = chat_histories[req.session_id]
        
        # Add user message to history
        history.append(HumanMessage(content=req.message))
        
        # Pass full history to MAXX orchestrator
        inputs = {"messages": list(history)}
        final_state = maxx_app.invoke(inputs)
        
        # Extract the AI response
        ai_response = final_state["messages"][-1].content
        
        # Handle list-type responses from Gemini
        if isinstance(ai_response, list):
            text_parts = [block.get("text", "") for block in ai_response if isinstance(block, dict) and block.get("type") == "text"]
            ai_response = "".join(text_parts) if text_parts else str(ai_response)
        
        # Store AI response in history
        history.append(AIMessage(content=ai_response))
        
        # Keep history manageable (last 20 messages)
        if len(history) > 20:
            chat_histories[req.session_id] = history[-20:]
        
        return {"response": ai_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_chat_history(session_id: str = "guest"):
    """Get chat history for a session"""
    history = chat_histories.get(session_id, [])
    return [
        {"sender": "user" if isinstance(msg, HumanMessage) else "bot", "text": msg.content}
        for msg in history
    ]

@router.delete("/history")
async def clear_chat_history(session_id: str = "guest"):
    """Clear chat history for a session"""
    chat_histories.pop(session_id, None)
    return {"status": "cleared"}
