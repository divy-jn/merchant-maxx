from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import re
from agents.maxx import maxx_app
from langchain_core.messages import HumanMessage
from utils.supabase_client import supabase
from middleware.auth_middleware import get_current_user
from utils.telemetry import AgentTelemetryHandler

router = APIRouter(prefix="/chat", tags=["chat"])
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
class ChatResponse(BaseModel):
    response: str
    conversation_id: str

CONFIRM_RE = re.compile(r"^(yes|y|yeah|yep|sure|okay|ok|proceed|go ahead|do it|confirm|confirmed|place it|buy it)\s*[.!]*$", re.I)

def verify_conversation_ownership(conv_id: str, current_user: dict):
    if not conv_id or conv_id == "guest":
        return
    conv_q = supabase.table("conversations").select("user_id").eq("id", conv_id).maybe_single().execute()
    conv = conv_q.data if conv_q else None
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    owner_id = conv.get("user_id")
    user_id = current_user.get("user_id") if current_user else None
    
    if owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

def _load_active_intent(conv_id: str):
    result = (supabase.table("purchase_intents").select("*").eq("conversation_id", conv_id)
              .in_("purchase_state", ["PURCHASE_PENDING", "RECOMMENDATION_SHOWN", "USER_CONFIRMED", "RECOVERY_PENDING", "PAYMENT_FAILED", "PAYMENT_UNKNOWN", "PRODUCT_SELECTED"])
              .order("created_at", desc=True).limit(1).execute())
    return result.data[0] if result.data else None

def _accept_latest_recommendation(intent: dict):
    rec_q = (supabase.table("recommendation_events").select("*").eq("session_id", intent["conversation_id"])
             .in_("status", ["SHOWN", "CLICKED"]).order("shown_at", desc=True).limit(1).execute())
    rec = rec_q.data[0] if rec_q.data else None
    if not rec:
        return intent
    product_q = (supabase.table("products").select("product_id,price_paise,active,inventory_qty")
                 .eq("product_id", rec["recommended_product_id"]).eq("merchant_id", "merchant_mxx_001").maybe_single().execute())
    product = product_q.data
    if not product or not product.get("active") or (product.get("inventory_qty") or 0) < 1:
        return intent
    basket = list(intent.get("basket") or [])
    if not any(x.get("product_id") == product["product_id"] for x in basket):
        basket.append({"product_id": product["product_id"], "quantity": 1})
    subtotal = 0
    for item in basket:
        p = (supabase.table("products").select("price_paise").eq("product_id", item["product_id"]).maybe_single().execute()).data
        if p: subtotal += int(p["price_paise"]) * int(item.get("quantity", 1))
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("recommendation_events").update({"status": "ACCEPTED", "accepted_at": now}).eq("recommendation_id", rec["recommendation_id"]).execute()
    supabase.table("purchase_intents").update({"basket": basket, "subtotal_paise": subtotal, "amount_paise": subtotal, "recommendation_id": rec["recommendation_id"], "purchase_state": "USER_CONFIRMED", "user_confirmed": True, "updated_at": now}).eq("purchase_intent_id", intent["purchase_intent_id"]).execute()
    return dict(intent, basket=basket, subtotal_paise=subtotal, amount_paise=subtotal, recommendation_id=rec["recommendation_id"], purchase_state="USER_CONFIRMED", user_confirmed=True)

@router.post("/", response_model=ChatResponse)
def chat_with_maxx(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        user_id = current_user.get("user_id") if current_user else None
        conv_id = req.conversation_id
        
        verify_conversation_ownership(conv_id, current_user)
        
        if not conv_id or conv_id == "guest":
            data = {"title": req.message[:50]}
            if user_id: data["user_id"] = user_id
            conv_id = supabase.table("conversations").insert(data).execute().data[0]["id"]
        supabase.table("messages").insert({"conversation_id": conv_id, "role": "user", "content": req.message}).execute()
        intent = _load_active_intent(conv_id)
        confirmed_now = bool(intent and intent.get("purchase_state") in {"PURCHASE_PENDING", "RECOMMENDATION_SHOWN"} and CONFIRM_RE.match(req.message.strip()))
        if confirmed_now:
            if intent.get("purchase_state") == "RECOMMENDATION_SHOWN":
                intent = _accept_latest_recommendation(intent)
            else:
                now = datetime.now(timezone.utc).isoformat()
                supabase.table("purchase_intents").update({"user_confirmed": True, "purchase_state": "USER_CONFIRMED", "updated_at": now}).eq("purchase_intent_id", intent["purchase_intent_id"]).execute()
                intent = dict(intent, user_confirmed=True, purchase_state="USER_CONFIRMED")

        context, purchase_state, user_confirmed = {}, "IDLE", False
        if intent:
            purchase_state = intent.get("purchase_state", "PURCHASE_PENDING")
            user_confirmed = bool(intent.get("user_confirmed"))
            context = {"purchase_intent_id": intent["purchase_intent_id"], "basket_items": intent.get("basket") or [], "amount_paise": int(intent.get("amount_paise") or 0), "intent_description": "Persisted purchase intent"}
        
        telemetry = AgentTelemetryHandler(conv_id)
        final_state = maxx_app.invoke({"messages": [HumanMessage(content=req.message)], "session_id": conv_id,
                                       "customer_id": (intent or {}).get("customer_id") or (current_user or {}).get("customer_id", ""),
                                       "purchase_state": purchase_state, "purchase_context": context, "user_confirmed": user_confirmed},
                                      config={"configurable": {"thread_id": conv_id}, "recursion_limit": 15, "callbacks": [telemetry]})
        response = final_state["messages"][-1].content if final_state.get("messages") else "How can I help?"
        if isinstance(response, list):
            response = "".join(b.get("text", "") for b in response if isinstance(b, dict) and b.get("type") == "text") or str(response)
        
        now_str = datetime.now(timezone.utc).isoformat()
        # Mark any GENERATED recommendations as SHOWN since they are now being delivered to the user
        supabase.table("recommendation_events").update({"status": "SHOWN", "shown_at": now_str}).eq("session_id", conv_id).eq("status", "GENERATED").execute()
        
        supabase.table("messages").insert({"conversation_id": conv_id, "role": "assistant", "content": str(response)}).execute()
        return ChatResponse(response=str(response), conversation_id=conv_id)
    except HTTPException:
        raise
    except Exception as exc:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/history")
def get_chat_history(conversation_id: str = None, current_user: dict = Depends(get_current_user)):
    if not supabase or not conversation_id or conversation_id == "guest": return []
    verify_conversation_ownership(conversation_id, current_user)
    res = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    return [{"sender": "user" if m["role"] == "user" else "bot", "text": m["content"]} for m in res.data]

@router.delete("/history")
def clear_chat_history(conversation_id: str, current_user: dict = Depends(get_current_user)):
    if not supabase or not conversation_id or conversation_id == "guest": return {"status": "cleared"}
    verify_conversation_ownership(conversation_id, current_user)
    supabase.table("conversations").delete().eq("id", conversation_id).execute()
    return {"status": "cleared"}

@router.get("/conversations")
def list_conversations(current_user: dict = Depends(get_current_user)):
    if not supabase or not current_user: return []
    return supabase.table("conversations").select("*").eq("user_id", current_user["user_id"]).order("updated_at", desc=True).execute().data
