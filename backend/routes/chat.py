from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from agents.maxx import maxx_app
from langchain_core.messages import HumanMessage

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

@router.post("/")
async def chat_with_maxx(req: ChatRequest):
    try:
        # Pass the human message to MAXX orchestrator
        inputs = {"messages": [HumanMessage(content=req.message)]}
        # In a real app we'd use checkpointer to store session history
        
        # We run the graph and get the final output
        final_state = maxx_app.invoke(inputs)
        
        # The last message is the AI response
        ai_response = final_state["messages"][-1].content
        
        return {"response": ai_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
