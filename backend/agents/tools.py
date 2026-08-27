import logging
import uuid
from typing import Annotated, Optional
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from search.vector_store import search_products_vector, pinecone_index, index_product
from cache.redis_client import cached
from agents.guardian import validate_action, GuardianException
from utils.supabase_client import supabase

logger = logging.getLogger(__name__)

def _ensure_catalog_indexed():
    if not pinecone_index: return
    try:
        if pinecone_index.describe_index_stats().total_vector_count == 0:
            from razorpay_service import items
            for item in items.list_items(count=100).get("items", []):
                index_product(item["id"], f"{item['name']} {item.get('description','')}", {
                    "name": item["name"], "description": item.get("description", ""),
                    "price": item["amount"] / 100, "currency": item["currency"],
                    "in_stock": item.get("active", True), "category": "General"
                })
    except Exception as exc:
        logger.warning("Pinecone catalog bootstrap skipped: %s", exc)
_ensure_catalog_indexed()

@tool
@cached(ttl=600)
def search_catalog(query: str, category: str = None) -> str:
    """Search the merchant catalog for products, prices and availability."""
    results = search_products_vector(query, top_k=5, category=category)
    if not results:
        try:
            from razorpay_service import items
            q = query.lower()
            for item in items.list_items(count=100).get("items", []):
                if q in item.get("name", "").lower() or q in item.get("description", "").lower():
                    results.append({"name": item["name"], "id": item["id"], "price": item["amount"]/100,
                                    "currency": item["currency"], "description": item.get("description", ""),
                                    "category": "General", "in_stock": item.get("active", True)})
                if len(results) >= 5: break
        except Exception as exc: logger.error("Catalog fallback failed: %s", exc)
    if not results: return "No products found matching your search."
    return "\n\n".join(f"- {p['name']} (ID: {p['id']})\n  Price: {p['currency']} {p['price']}\n  Category: {p.get('category','General')}\n  Description: {p.get('description','')}\n  In Stock: {'Yes' if p.get('in_stock',True) else 'No'}" for p in results)

@tool
def get_product_details(item_id: str):
    """Get full details for a catalog product."""
    try:
        from razorpay_service import items
        item = items.fetch_item(item_id)
        return f"Product: {item['name']}\nPrice: Rs.{item['amount']/100:,.2f}\nDescription: {item.get('description','N/A')}\nProduct ID: {item['id']}\nStatus: {'Available' if item.get('active',True) else 'Unavailable'}"
    except Exception as exc: return f"Error fetching product details: {exc}"

@tool
def stage_purchase_intent(product_id: str, amount_paise: int) -> str:
    """Stage a product for checkout; this never authorizes payment."""
    return f"Purchase intent staged for {product_id}. Await explicit confirmation."

@tool
def fetch_recommendations(state: Annotated[dict, InjectedState], customer_id: str = None, category: str = None) -> str:
    """Return evidence-backed cross-sell recommendations and record their lifecycle."""
    ctx = state.get("purchase_context", {}); basket = ctx.get("basket_items", [])
    if not basket or not supabase: return "No data-backed recommendations are currently available."
    product_id = basket[0]["product_id"]
    try:
        rows = supabase.table("product_affinity").select("*").eq("product_id", product_id).order("lift_score", desc=True).limit(5).execute().data or []
        candidates = []
        for row in rows:
            p = (supabase.table("products").select("product_id,name,price_paise,description,inventory_qty,active,category")
                 .eq("product_id", row["related_product_id"]).eq("merchant_id", "merchant_mxx_001").maybe_single().execute()).data
            if p and p.get("active") and (p.get("inventory_qty") or 0) > 0 and p["product_id"] != product_id: candidates.append((row,p))
        if not candidates: return "No sufficiently strong in-stock data-backed recommendation was found."
        lines=[]
        for row,p in candidates[:2]:
            rec_id=f"rec_{uuid.uuid4().hex[:12]}"
            supabase.table("recommendation_events").insert({"recommendation_id":rec_id,"session_id":state.get("session_id"),"customer_id":customer_id or state.get("customer_id"),"merchant_id":"merchant_mxx_001","source_product_id":product_id,"recommended_product_id":p["product_id"],"recommendation_type":"CROSS_SELL","agent_name":"Booster","score":row.get("lift_score",0),"reason":f"Observed co-purchase affinity; lift={row.get('lift_score',0)}","status":"GENERATED"}).execute()
            lines.append(f"- {p['name']} (Rs.{p['price_paise']/100:,.2f}) [Rec ID: {rec_id}] — evidence lift {row.get('lift_score',0):.3f}")
        return "Data-backed recommendations:\n"+"\n".join(lines)
    except Exception as exc: return f"Recommendation service unavailable: {exc}"

@tool
def analyze_campaign_opportunities() -> str:
    """Find merchant growth opportunities from persisted customer metrics."""
    if not supabase: return "Database connection not available."
    try:
        rows=supabase.table("customer_metrics").select("customer_id,segment,lifetime_value_paise,churn_probability,preferred_category").order("lifetime_value_paise",desc=True).limit(10).execute().data or []
        return "Detected high-value/churn opportunities:\n"+"\n".join(f"- {c['customer_id']} | segment={c.get('segment')} | LTV=Rs.{(c.get('lifetime_value_paise') or 0)/100:,.2f} | churn={c.get('churn_probability',0):.2f} | category={c.get('preferred_category')}" for c in rows) if rows else "No campaign opportunities found."
    except Exception as exc: return f"Error analyzing campaign opportunities: {exc}"

@tool
def create_razorpay_order(state: Annotated[dict, InjectedState], customer_email: Optional[str]=None, customer_contact: Optional[str]=None):
    """Create a Razorpay order only after server-side basket and Guardian validation."""
    if not supabase: return "Order blocked: Supabase is unavailable."
    ctx=state.get("purchase_context") or {}; intent_id=ctx.get("purchase_intent_id")
    if not intent_id: return "Order blocked: missing purchase_intent_id."
    try:
        intent=(supabase.table("purchase_intents").select("*").eq("purchase_intent_id",intent_id).maybe_single().execute()).data
        if not intent: return "Order blocked: purchase intent not found."
        basket=intent.get("basket") or []
        if intent.get("purchase_state")!="USER_CONFIRMED" or not intent.get("user_confirmed"): return "Order blocked by Guardian: explicit confirmation is required."
        existing=supabase.table("orders").select("order_id").eq("purchase_intent_id",intent_id).limit(1).execute().data or []
        if existing:
            validate_action("Closer","create_razorpay_order",{"purchase_intent_id":intent_id,"user_confirmed":True,"purchase_state":"USER_CONFIRMED","is_duplicate":True},int(intent.get("amount_paise") or 0))
        if not basket: return "Order blocked: empty basket."
        subtotal=0; validated=[]
        for entry in basket:
            pid=entry["product_id"]; qty=int(entry.get("quantity",1))
            p=(supabase.table("products").select("*").eq("product_id",pid).eq("merchant_id","merchant_mxx_001").maybe_single().execute()).data
            if not p or not p.get("active") or (p.get("inventory_qty") or 0)<qty: return "Order blocked by Guardian: product unavailable or insufficient inventory."
            unit=int(p["price_paise"]); line=unit*qty; subtotal+=line; validated.append((p,qty,unit,line))
        discount=int(intent.get("discount_paise") or 0); tax=int(intent.get("tax_paise") or 0); total=subtotal-discount+tax
        if total<=0 or int(intent.get("amount_paise") or 0)!=total: return "Order blocked by Guardian: server-calculated basket total does not match purchase intent."
        validate_action("Closer","create_razorpay_order",{"purchase_intent_id":intent_id,"user_confirmed":True,"purchase_state":"USER_CONFIRMED","entity_valid":True},total)
        from razorpay_service import orders
        notes={"purchase_intent_id":intent_id,"merchant_id":"merchant_mxx_001"}
        if customer_email: notes["customer_email"]=customer_email
        if customer_contact: notes["customer_contact"]=customer_contact
        rzp_order=orders.create_order(total,"INR",receipt=intent_id,notes=notes)
        local_id=f"ord_{uuid.uuid4().hex[:12]}"
        supabase.table("orders").insert({"order_id":local_id,"purchase_intent_id":intent_id,"merchant_id":"merchant_mxx_001","customer_id":intent.get("customer_id"),"status":"CREATED","subtotal_paise":subtotal,"discount_paise":discount,"tax_paise":tax,"total_paise":total,"currency":"INR","source":"AI_AGENT","purchase_state":"ORDER_CREATED"}).execute()
        for p,qty,unit,line in validated:
            supabase.table("order_items").insert({"order_item_id":f"oi_{uuid.uuid4().hex[:12]}","order_id":local_id,"product_id":p["product_id"],"quantity":qty,"unit_price_paise":unit,"discount_paise":0,"total_paise":line}).execute()
        supabase.table("entity_mapping").insert({"synthetic_id":local_id,"entity_type":"order","razorpay_id":rzp_order["id"]}).execute()
        supabase.table("purchase_intents").update({"purchase_state":"PAYMENT_PENDING","razorpay_order_id":rzp_order["id"]}).eq("purchase_intent_id",intent_id).execute()
        return f"Razorpay Order created successfully. Order ID: {rzp_order['id']}\nAmount: Rs.{total/100:,.2f}\nLocal order: {local_id}\nPayment is pending; verify Razorpay status before treating it as successful."
    except GuardianException as exc: return f"Order blocked by Guardian: {exc}"
    except Exception as exc: logger.exception("Razorpay order creation failed"); return f"Error creating order: {exc}"

@tool
def check_payment_status(state: Annotated[dict, InjectedState]) -> str:
    """Inspect Razorpay state without initiating a payment."""
    ctx=state.get("purchase_context") or {}; iid=ctx.get("purchase_intent_id")
    if not iid or not supabase: return "Unable to inspect payment state."
    try:
        intent=(supabase.table("purchase_intents").select("*").eq("purchase_intent_id",iid).maybe_single().execute()).data
        if not intent or not intent.get("razorpay_order_id"): return "No Razorpay order exists for this purchase intent."
        from razorpay_service import orders
        rid=intent["razorpay_order_id"]; ps=orders.fetch_order_payments(rid).get("items",[])
        if any(p.get("status")=="captured" for p in ps): return f"PAYMENT_SUCCESS: {rid} has a captured payment."
        if ps and all(p.get("status")=="failed" for p in ps): return f"PAYMENT_FAILED: {rid} has only failed payments. Do not retry this intent."
        return f"PAYMENT_UNKNOWN: {rid} requires state inspection."
    except Exception as exc: return f"PAYMENT_UNKNOWN: unable to verify safely ({exc})."

@tool
def reset_purchase_intent(state: Annotated[dict, InjectedState]) -> str:
    """Create a fresh intent only after a FAILED/UNKNOWN state has been inspected."""
    if not supabase: return "Unable to reset purchase intent."
    old_id=(state.get("purchase_context") or {}).get("purchase_intent_id")
    if not old_id: return "No purchase intent to reset."
    try:
        old=(supabase.table("purchase_intents").select("*").eq("purchase_intent_id",old_id).maybe_single().execute()).data
        if not old or old.get("purchase_state") not in {"PAYMENT_FAILED","PAYMENT_UNKNOWN","RECOVERY_PENDING"}: return "Reset blocked: payment state has not been resolved."
        new_id=f"pi_{uuid.uuid4().hex[:12]}"; row={k:old.get(k) for k in ("conversation_id","customer_id","merchant_id","basket","subtotal_paise","discount_paise","tax_paise","amount_paise")}; row.update({"purchase_intent_id":new_id,"purchase_state":"PURCHASE_PENDING","user_confirmed":False})
        supabase.table("purchase_intents").insert(row).execute()
        return f"Fresh purchase intent created: {new_id}. Explicit confirmation is required again."
    except Exception as exc: return f"Unable to reset purchase intent: {exc}"

SCOUT_TOOLS=[search_catalog,get_product_details,stage_purchase_intent]
BOOSTER_TOOLS=[fetch_recommendations]
CAMPAIGNER_TOOLS=[analyze_campaign_opportunities]
PAYMENT_TOOLS=[create_razorpay_order,check_payment_status,reset_purchase_intent]
DISCOVERY_TOOLS=SCOUT_TOOLS+BOOSTER_TOOLS+CAMPAIGNER_TOOLS
ALL_TOOLS=DISCOVERY_TOOLS+PAYMENT_TOOLS
