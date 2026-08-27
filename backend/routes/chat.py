from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional
from agents.maxx import maxx_app
from langchain_core.messages import HumanMessage, AIMessage
from utils.supabase_client import supabase
from middleware.auth_middleware import get_current_user
import uuid

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

@router.post("/", response_model=ChatResponse)
async def chat_with_maxx(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    try:
        user_id = current_user["user_id"] if current_user else None
        
        # 1. Get or create conversation
        conv_id = req.conversation_id
        if not conv_id or conv_id == "guest":
            # Create new conversation
            conv_data = {"title": req.message[:50]}
            if user_id:
                conv_data["user_id"] = user_id
            res = supabase.table("conversations").insert(conv_data).execute()
            conv_id = res.data[0]["id"]
        
        # 2. Add user message to DB
        supabase.table("messages").insert({
            "conversation_id": conv_id,
            "role": "user",
            "content": req.message
        }).execute()
        
        # 3. Load history for MAXX (last 20 messages)
        msg_res = supabase.table("messages").select("*").eq("conversation_id", conv_id).order("created_at", desc=True).limit(20).execute()
        db_messages = reversed(msg_res.data) # Chronological order
        
        langchain_history = []
        for m in db_messages:
            if m["role"] == "user":
                langchain_history.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                langchain_history.append(AIMessage(content=m["content"]))
        
        # 4. Invoke MAXX
        inputs = {"messages": langchain_history}
        final_state = maxx_app.invoke(inputs)
        
        ai_response = final_state["messages"][-1].content
        if isinstance(ai_response, list):
            text_parts = [block.get("text", "") for block in ai_response if isinstance(block, dict) and block.get("type") == "text"]
            ai_response = "".join(text_parts) if text_parts else str(ai_response)
            
        # 5. Store AI response in DB
        supabase.table("messages").insert({
            "conversation_id": conv_id,
            "role": "assistant",
            "content": ai_response
        }).execute()
        
        return ChatResponse(response=ai_response, conversation_id=conv_id)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_chat_history(conversation_id: str = None, current_user: dict = Depends(get_current_user)):
    """Get chat history for a conversation"""
    if not supabase or not conversation_id or conversation_id == "guest":
        return []
        
    msg_res = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    
    return [
        {"sender": "user" if m["role"] == "user" else "bot", "text": m["content"]}
        for m in msg_res.data
    ]

@router.delete("/history")
async def clear_chat_history(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a conversation"""
    if not supabase or not conversation_id or conversation_id == "guest":
        return {"status": "cleared"}
        
    supabase.table("conversations").delete().eq("id", conversation_id).execute()
    return {"status": "cleared"}

@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    """List all conversations for the current user"""
    if not supabase or not current_user:
        return []
        
    res = supabase.table("conversations").select("*").eq("user_id", current_user["user_id"]).order("updated_at", desc=True).execute()
    return res.data
