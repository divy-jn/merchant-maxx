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
class CheckoutItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price_paise: int

class CheckoutData(BaseModel):
    type: str = "checkout"
    order_id: str
    amount_paise: int
    currency: str = "INR"
    items: list[CheckoutItem]

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    checkout_data: Optional[CheckoutData] = None

CONFIRM_RE = re.compile(r"^(yes|y|yeah|yep|sure|okay|ok|proceed|go ahead|do it|confirm|confirmed|place it|buy it|i want to buy it|purchase it|complete the order|pay now|checkout)\s*[.!]*$", re.I)

def verify_conversation_ownership(conv_id: str, current_user: dict):
    if not conv_id or conv_id == "guest":
        return
    try:
        conv_q = supabase.table("conversations").select("user_id").eq("id", conv_id).maybe_single().execute()
        conv = conv_q.data if conv_q else None
    except Exception as e:
        # Check if it is a postgrest APIError for invalid UUID
        if hasattr(e, 'code') and getattr(e, 'code') == '22P02':
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        if '22P02' in str(e):
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        raise e
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    owner_id = conv.get("user_id")
    user_id = current_user.get("user_id") if current_user else None
    
    if owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

def _load_active_intent(conv_id: str):
    result = (supabase.table("purchase_intents").select("*").eq("conversation_id", conv_id)
              .in_("purchase_state", ["PURCHASE_PENDING", "RECOMMENDATION_SHOWN", "USER_CONFIRMED", "RECOVERY_PENDING", "PAYMENT_FAILED", "PAYMENT_UNKNOWN", "PRODUCT_SELECTED", "ORDER_CREATING", "ORDER_CREATED", "PAYMENT_PENDING"])
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
        p_res = supabase.table("products").select("price_paise").eq("product_id", item["product_id"]).maybe_single().execute()
        p = getattr(p_res, "data", None) if p_res is not None else None
        if p: subtotal += int(p["price_paise"]) * int(item.get("quantity", 1))
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("recommendation_events").update({"status": "ACCEPTED", "accepted_at": now}).eq("recommendation_id", rec["recommendation_id"]).execute()
    
    # ── ATOMIC CONDITIONAL UPDATE ──
    # Prevents downgrading a terminal PAYMENT_SUCCESS if a webhook resolved it concurrently.
    res = supabase.table("purchase_intents").update({
        "basket": basket, 
        "subtotal_paise": subtotal, 
        "amount_paise": subtotal, 
        "recommendation_id": rec["recommendation_id"], 
        "purchase_state": "USER_CONFIRMED", 
        "user_confirmed": True, 
        "confirmed_basket": basket, 
        "confirmed_amount_paise": subtotal, 
        "confirmation_timestamp": now, 
        "updated_at": now
    }).eq("purchase_intent_id", intent["purchase_intent_id"]).neq("purchase_state", "PAYMENT_SUCCESS").execute()
    
    if not res.data:
        # If the update failed, it was likely locked or succeeded already. We reload to avoid returning stale state.
        fresh_intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
        if fresh_intent and fresh_intent.data:
            return fresh_intent.data

    return dict(intent, basket=basket, subtotal_paise=subtotal, amount_paise=subtotal, recommendation_id=rec["recommendation_id"], purchase_state="USER_CONFIRMED", user_confirmed=True, confirmed_basket=basket, confirmed_amount_paise=subtotal)

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
                res = supabase.table("purchase_intents").update({
                    "user_confirmed": True, 
                    "purchase_state": "USER_CONFIRMED", 
                    "confirmed_basket": intent.get("basket"), 
                    "confirmed_amount_paise": intent.get("amount_paise"), 
                    "confirmation_timestamp": now, 
                    "updated_at": now
                }).eq("purchase_intent_id", intent["purchase_intent_id"]).in_("purchase_state", ["PURCHASE_PENDING", "RECOMMENDATION_SHOWN"]).execute()
                
                if res.data:
                    intent = dict(intent, user_confirmed=True, purchase_state="USER_CONFIRMED", confirmed_basket=intent.get("basket"), confirmed_amount_paise=intent.get("amount_paise"))
                else:
                    # Update failed due to atomic guard, reload intent
                    fresh = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
                    if fresh and fresh.data:
                        intent = fresh.data

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
        
        # Determine structured checkout data by inspecting fresh state
        checkout_data = None
        if intent:
            fresh_intent_res = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
            fresh_intent = fresh_intent_res.data if fresh_intent_res else None
            if fresh_intent and fresh_intent.get("purchase_state") in {"PAYMENT_PENDING", "PAYMENT_FAILED", "ORDER_CREATED"} and fresh_intent.get("razorpay_order_id"):
                basket = fresh_intent.get("basket") or []
                items = []
                for b_item in basket:
                    pid = b_item["product_id"]
                    qty = b_item.get("quantity", 1)
                    p_res = supabase.table("products").select("name,price_paise").eq("product_id", pid).maybe_single().execute()
                    p_data = p_res.data if p_res else {}
                    items.append({
                        "product_id": pid,
                        "name": p_data.get("name", pid),
                        "quantity": qty,
                        "unit_price_paise": p_data.get("price_paise", 0)
                    })
                checkout_data = CheckoutData(
                    order_id=fresh_intent["razorpay_order_id"],
                    amount_paise=fresh_intent["amount_paise"],
                    items=items
                )

        return ChatResponse(response=str(response), conversation_id=conv_id, checkout_data=checkout_data)
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
    messages = [{"sender": "user" if m["role"] == "user" else "bot", "text": m["content"]} for m in res.data]
    
    intent = _load_active_intent(conversation_id)
    if intent and intent.get("purchase_state") in {"PAYMENT_PENDING", "PAYMENT_FAILED", "ORDER_CREATED"} and intent.get("razorpay_order_id"):
        basket = intent.get("basket") or []
        items = []
        for b_item in basket:
            pid = b_item["product_id"]
            qty = b_item.get("quantity", 1)
            p_res = supabase.table("products").select("name,price_paise").eq("product_id", pid).maybe_single().execute()
            p_data = p_res.data if p_res else {}
            items.append({
                "product_id": pid,
                "name": p_data.get("name", pid),
                "quantity": qty,
                "unit_price_paise": p_data.get("price_paise", 0)
            })
        messages.append({
            "sender": "bot",
            "text": "Your order is ready for payment.",
            "checkout_data": {
                "type": "checkout",
                "order_id": intent["razorpay_order_id"],
                "amount_paise": intent["amount_paise"],
                "currency": "INR",
                "items": items
            }
        })
    return messages

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
