from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import re
from agents.maxx import maxx_app
from langchain_core.messages import HumanMessage
from utils.supabase_client import supabase
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
class ChatResponse(BaseModel):
    response: str
    conversation_id: str

CONFIRM_RE = re.compile(r"^(yes|y|yeah|yep|sure|okay|ok|proceed|go ahead|do it|confirm|confirmed|place it|buy it)\s*[.!]*$", re.I)

def _load_active_intent(conv_id: str):
    result = (supabase.table("purchase_intents").select("*").eq("conversation_id", conv_id)
              .in_("purchase_state", ["PURCHASE_PENDING", "RECOMMENDATION_SHOWN", "USER_CONFIRMED", "RECOVERY_PENDING", "PAYMENT_FAILED", "PAYMENT_UNKNOWN"])
              .order("created_at", desc=True).limit(1).execute())
    return result.data[0] if result.data else None

@router.post("/", response_model=ChatResponse)
async def chat_with_maxx(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        user_id = current_user.get("user_id") if current_user else None
        conv_id = req.conversation_id
        if not conv_id or conv_id == "guest":
            data = {"title": req.message[:50]}
            if user_id: data["user_id"] = user_id
            conv_id = supabase.table("conversations").insert(data).execute().data[0]["id"]
        supabase.table("messages").insert({"conversation_id": conv_id, "role": "user", "content": req.message}).execute()

        intent = _load_active_intent(conv_id)
        confirmed_now = bool(intent and intent.get("purchase_state") == "PURCHASE_PENDING" and CONFIRM_RE.match(req.message.strip()))
        if confirmed_now:
            supabase.table("purchase_intents").update({"user_confirmed": True, "purchase_state": "USER_CONFIRMED"}).eq("purchase_intent_id", intent["purchase_intent_id"]).execute()
            intent = dict(intent, user_confirmed=True, purchase_state="USER_CONFIRMED")

        context, purchase_state, user_confirmed = {}, "IDLE", False
        if intent:
            purchase_state = intent.get("purchase_state", "PURCHASE_PENDING")
            user_confirmed = bool(intent.get("user_confirmed"))
            context = {"purchase_intent_id": intent["purchase_intent_id"], "basket_items": intent.get("basket") or [],
                       "amount_paise": int(intent.get("amount_paise") or 0), "intent_description": "Persisted purchase intent"}
        final_state = maxx_app.invoke({"messages": [HumanMessage(content=req.message)], "session_id": conv_id,
                                       "customer_id": (intent or {}).get("customer_id") or (current_user or {}).get("customer_id", ""),
                                       "purchase_state": purchase_state, "purchase_context": context,
                                       "user_confirmed": user_confirmed},
                                      config={"configurable": {"thread_id": conv_id}})
        response = final_state["messages"][-1].content if final_state.get("messages") else "How can I help?"
        if isinstance(response, list):
            response = "".join(b.get("text", "") for b in response if isinstance(b, dict) and b.get("type") == "text") or str(response)
        supabase.table("messages").insert({"conversation_id": conv_id, "role": "assistant", "content": str(response)}).execute()
        return ChatResponse(response=str(response), conversation_id=conv_id)
    except Exception as exc:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/history")
async def get_chat_history(conversation_id: str = None, current_user: dict = Depends(get_current_user)):
    if not supabase or not conversation_id or conversation_id == "guest": return []
    res = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    return [{"sender": "user" if m["role"] == "user" else "bot", "text": m["content"]} for m in res.data]

@router.delete("/history")
async def clear_chat_history(conversation_id: str, current_user: dict = Depends(get_current_user)):
    if not supabase or not conversation_id or conversation_id == "guest": return {"status": "cleared"}
    supabase.table("conversations").delete().eq("id", conversation_id).execute()
    return {"status": "cleared"}

@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    if not supabase or not current_user: return []
    return supabase.table("conversations").select("*").eq("user_id", current_user["user_id"]).order("updated_at", desc=True).execute().data
