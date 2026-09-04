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
    purchase_intent_id: str
    order_id: str
    amount_paise: int
    currency: str = "INR"
    items: list[CheckoutItem]

class ChatAction(BaseModel):
    type: str
    label: str
    payload: Optional[dict] = None

class ActionRequest(BaseModel):
    conversation_id: str
    action: str
    payload: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    checkout_data: Optional[CheckoutData] = None
    actions: Optional[list[ChatAction]] = None
    purchase_state: Optional[str] = None

CONFIRM_RE = re.compile(r"^(yes|y|yeah|yep|sure|okay|ok|proceed|go ahead|do it|confirm|confirmed|place it|buy it|i want to buy it|purchase it|complete the order|pay now|checkout)\s*[.!]*$", re.I)

def verify_conversation_ownership(conv_id: str, current_user: dict):
    if not conv_id or conv_id == "guest":
        return
    try:
        conv_q = supabase.table("conversations").select("user_id").eq("id", conv_id).maybe_single().execute()
        conv = conv_q.data if conv_q else None
    except Exception as e:
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
        fresh_intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
        if fresh_intent and fresh_intent.data:
            return fresh_intent.data

    return dict(intent, basket=basket, subtotal_paise=subtotal, amount_paise=subtotal, recommendation_id=rec["recommendation_id"], purchase_state="USER_CONFIRMED", user_confirmed=True, confirmed_basket=basket, confirmed_amount_paise=subtotal)

def _get_checkout_data(intent: dict) -> Optional[CheckoutData]:
    if not intent or intent.get("purchase_state") not in {"PAYMENT_PENDING", "PAYMENT_FAILED", "ORDER_CREATED"} or not intent.get("razorpay_order_id"):
        return None
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
    return CheckoutData(
        purchase_intent_id=intent["purchase_intent_id"],
        order_id=intent["razorpay_order_id"],
        amount_paise=intent["amount_paise"],
        items=items
    )

def _get_actions_for_state(purchase_state: str, intent_id: str) -> list[ChatAction]:
    actions = []
    if purchase_state == "PRODUCT_SELECTED":
        actions.append(ChatAction(type="ADD_TO_CART", label="Add to Cart", payload={"purchase_intent_id": intent_id}))
        actions.append(ChatAction(type="BUY_NOW", label="Buy Now", payload={"purchase_intent_id": intent_id}))
    elif purchase_state in {"PURCHASE_PENDING", "RECOMMENDATION_SHOWN"}:
        actions.append(ChatAction(type="PROCEED_TO_CHECKOUT", label="Proceed to Checkout", payload={"purchase_intent_id": intent_id}))
        actions.append(ChatAction(type="ADD_MORE_ITEMS", label="Add More Items", payload={"purchase_intent_id": intent_id}))
    elif purchase_state == "USER_CONFIRMED":
        actions.append(ChatAction(type="PROCEED_TO_CHECKOUT", label="Proceed to Payment", payload={"purchase_intent_id": intent_id}))
        actions.append(ChatAction(type="MODIFY_CART", label="Modify Cart", payload={"purchase_intent_id": intent_id}))
    return actions

@router.post("/action", response_model=ChatResponse)
def handle_action(req: ActionRequest, current_user: dict = Depends(get_current_user)):
    if not supabase: raise HTTPException(status_code=503, detail="Supabase not configured")
    verify_conversation_ownership(req.conversation_id, current_user)
    
    intent_id = req.payload.get("purchase_intent_id") if req.payload else None
    if not intent_id:
        intent = _load_active_intent(req.conversation_id)
    else:
        intent_res = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).maybe_single().execute()
        intent = intent_res.data if intent_res else None
        
    if not intent or intent.get("conversation_id") != req.conversation_id:
        raise HTTPException(status_code=400, detail="Invalid or stale purchase intent")
    
    current_state = intent.get("purchase_state")
    now = datetime.now(timezone.utc).isoformat()
    response_text = ""
    
    if req.action == "ADD_TO_CART":
        if current_state == "PRODUCT_SELECTED":
            supabase.table("purchase_intents").update({"purchase_state": "PURCHASE_PENDING", "updated_at": now}).eq("purchase_intent_id", intent["purchase_intent_id"]).execute()
            basket = intent.get("basket") or []
            basket_desc = ", ".join(f"{item.get('quantity', 1)}x {item.get('product_id', '')}" for item in basket)
            response_text = f"Added to your cart: {basket_desc}. You can add more items or proceed to checkout when ready."
            supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()
        else:
            response_text = "Cart is already updated."

    elif req.action == "BUY_NOW":
        # Direct checkout: confirm + create order in one step
        if current_state in {"PRODUCT_SELECTED", "PURCHASE_PENDING", "RECOMMENDATION_SHOWN"}:
            res = supabase.table("purchase_intents").update({
                "user_confirmed": True,
                "purchase_state": "USER_CONFIRMED",
                "confirmed_basket": intent.get("basket"),
                "confirmed_amount_paise": intent.get("amount_paise"),
                "confirmation_timestamp": now,
                "updated_at": now
            }).eq("purchase_intent_id", intent["purchase_intent_id"]).in_("purchase_state", ["PRODUCT_SELECTED", "PURCHASE_PENDING", "RECOMMENDATION_SHOWN"]).execute()
            if res.data:
                intent["purchase_state"] = "USER_CONFIRMED"
                intent["user_confirmed"] = True
            from agents.tools import create_razorpay_order
            injected_state = {"purchase_context": {"purchase_intent_id": intent["purchase_intent_id"]}, "session_id": req.conversation_id}
            rzp_response = create_razorpay_order.invoke({"state": injected_state})
            response_text = str(rzp_response)
            supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()
        elif current_state == "USER_CONFIRMED":
            from agents.tools import create_razorpay_order
            injected_state = {"purchase_context": {"purchase_intent_id": intent["purchase_intent_id"]}, "session_id": req.conversation_id}
            rzp_response = create_razorpay_order.invoke({"state": injected_state})
            response_text = str(rzp_response)
            supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()
        else:
            response_text = "Cannot proceed with Buy Now at this stage."

    elif req.action == "PROCEED_TO_CHECKOUT":
        if current_state in {"PURCHASE_PENDING", "RECOMMENDATION_SHOWN"}:
            if current_state == "RECOMMENDATION_SHOWN":
                intent = _accept_latest_recommendation(intent)
            else:
                res = supabase.table("purchase_intents").update({
                    "user_confirmed": True,
                    "purchase_state": "USER_CONFIRMED",
                    "confirmed_basket": intent.get("basket"),
                    "confirmed_amount_paise": intent.get("amount_paise"),
                    "confirmation_timestamp": now,
                    "updated_at": now
                }).eq("purchase_intent_id", intent["purchase_intent_id"]).in_("purchase_state", ["PURCHASE_PENDING", "RECOMMENDATION_SHOWN"]).execute()
                if not res.data:
                    fresh = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
                    if fresh and fresh.data:
                        intent = fresh.data
                else:
                    intent["purchase_state"] = "USER_CONFIRMED"
            
            from agents.tools import create_razorpay_order
            injected_state = {"purchase_context": {"purchase_intent_id": intent["purchase_intent_id"]}, "session_id": req.conversation_id}
            rzp_response = create_razorpay_order.invoke({"state": injected_state})
            response_text = str(rzp_response)
            supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()
        elif current_state == "USER_CONFIRMED":
            # Already confirmed — just create the order without re-confirming
            from agents.tools import create_razorpay_order
            injected_state = {"purchase_context": {"purchase_intent_id": intent["purchase_intent_id"]}, "session_id": req.conversation_id}
            rzp_response = create_razorpay_order.invoke({"state": injected_state})
            response_text = str(rzp_response)
            supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()
        else:
            response_text = "Checkout already in progress."

    elif req.action == "ADD_MORE_ITEMS":
        response_text = "Sure! Tell me what else you'd like to add, or browse the catalog."
        supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()

    elif req.action == "MODIFY_CART":
        if current_state == "USER_CONFIRMED":
            supabase.table("purchase_intents").update({
                "user_confirmed": False,
                "purchase_state": "PURCHASE_PENDING",
                "confirmed_basket": None,
                "confirmed_amount_paise": None,
                "confirmation_timestamp": None,
                "updated_at": now
            }).eq("purchase_intent_id", intent["purchase_intent_id"]).eq("purchase_state", "USER_CONFIRMED").execute()
        response_text = "Your cart is now unlocked for changes. Tell me what you'd like to modify."
        supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()

    elif req.action == "VERIFY_PAYMENT":
        if current_state in {"PAYMENT_PENDING", "PAYMENT_SUCCESS", "ORDER_CREATED"}:
            from agents.tools import check_payment_status
            injected_state = {"purchase_context": {"purchase_intent_id": intent["purchase_intent_id"]}, "session_id": req.conversation_id}
            response_text = check_payment_status(injected_state)
            supabase.table("messages").insert({"conversation_id": req.conversation_id, "role": "assistant", "content": response_text}).execute()
        else:
            response_text = "No pending payment found."
            
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    fresh_intent_res = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
    fresh_intent = fresh_intent_res.data if fresh_intent_res else None
    
    actions = _get_actions_for_state(fresh_intent.get("purchase_state"), fresh_intent["purchase_intent_id"]) if fresh_intent else []
    checkout_data = _get_checkout_data(fresh_intent)
    
    return ChatResponse(
        response=response_text,
        conversation_id=req.conversation_id,
        checkout_data=checkout_data,
        actions=actions,
        purchase_state=fresh_intent.get("purchase_state") if fresh_intent else None
    )

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
        # Also detect confirmation when already USER_CONFIRMED (prevents re-asking)
        already_confirmed = bool(intent and intent.get("purchase_state") == "USER_CONFIRMED" and intent.get("user_confirmed") and CONFIRM_RE.match(req.message.strip()))

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
                    fresh = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
                    if fresh and fresh.data:
                        intent = fresh.data

        # ── DETERMINISTIC CHECKOUT: skip the LLM entirely when user has confirmed ──
        # This prevents the Closer from re-asking for confirmation.
        if confirmed_now or already_confirmed:
            from agents.tools import create_razorpay_order
            injected_state = {"purchase_context": {"purchase_intent_id": intent["purchase_intent_id"]}, "session_id": conv_id}
            rzp_response = str(create_razorpay_order.invoke({"state": injected_state}))
            supabase.table("messages").insert({"conversation_id": conv_id, "role": "assistant", "content": rzp_response}).execute()

            fresh_intent_res = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
            fresh_intent = fresh_intent_res.data if fresh_intent_res else None
            checkout_data = _get_checkout_data(fresh_intent)
            actions = _get_actions_for_state(fresh_intent.get("purchase_state"), fresh_intent["purchase_intent_id"]) if fresh_intent else []

            return ChatResponse(
                response=rzp_response,
                conversation_id=conv_id,
                checkout_data=checkout_data,
                actions=actions,
                purchase_state=fresh_intent.get("purchase_state") if fresh_intent else "USER_CONFIRMED"
            )

        # ── Normal LLM path (non-confirmation messages) ──
        context, purchase_state, user_confirmed = {}, "IDLE", False
        if intent:
            # Use the LATEST state from intent (may have been updated above)
            purchase_state = intent.get("purchase_state", "IDLE")
            user_confirmed = bool(intent.get("user_confirmed"))
            context = {"purchase_intent_id": intent["purchase_intent_id"], "basket_items": intent.get("basket") or [], "amount_paise": int(intent.get("amount_paise") or 0), "intent_description": "Persisted purchase intent"}
        
        import logging
        logger = logging.getLogger(__name__)
        try:
            telemetry = AgentTelemetryHandler(conv_id)
            final_state = maxx_app.invoke({"messages": [HumanMessage(content=req.message)], "session_id": conv_id,
                                           "customer_id": (intent or {}).get("customer_id") or user_id or "",
                                           "purchase_state": purchase_state, "purchase_context": context, "user_confirmed": user_confirmed},
                                          config={"configurable": {"thread_id": conv_id}, "recursion_limit": 15, "callbacks": [telemetry]})
            response = final_state["messages"][-1].content if final_state.get("messages") else "How can I help?"
            if isinstance(response, list):
                response = "".join(b.get("text", "") for b in response if isinstance(b, dict) and b.get("type") == "text") or str(response)
        except Exception as e:
            logger.error(f"LLM Provider Error: {type(e).__name__} - {e}")
            response = "I am currently experiencing technical difficulties. Please try again later."
        
        now_str = datetime.now(timezone.utc).isoformat()
        supabase.table("recommendation_events").update({"status": "SHOWN", "shown_at": now_str}).eq("session_id", conv_id).eq("status", "GENERATED").execute()
        
        supabase.table("messages").insert({"conversation_id": conv_id, "role": "assistant", "content": str(response)}).execute()
        
        checkout_data = None
        actions = []
        final_purchase_state = purchase_state
        if intent:
            fresh_intent_res = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent["purchase_intent_id"]).maybe_single().execute()
            fresh_intent = fresh_intent_res.data if fresh_intent_res else None
            checkout_data = _get_checkout_data(fresh_intent)
            actions = _get_actions_for_state(fresh_intent.get("purchase_state"), fresh_intent["purchase_intent_id"]) if fresh_intent else []
            if fresh_intent:
                final_purchase_state = fresh_intent.get("purchase_state")

        return ChatResponse(
            response=str(response),
            conversation_id=conv_id,
            checkout_data=checkout_data,
            actions=actions,
            purchase_state=final_purchase_state
        )
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
    checkout_data = _get_checkout_data(intent)
    if checkout_data:
        if intent.get("purchase_state") in {"PAYMENT_PENDING", "PAYMENT_FAILED", "ORDER_CREATED"}:
            messages.append({
                "sender": "bot",
                "text": "Your order is ready for payment.",
                "checkout_data": checkout_data.model_dump()
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
