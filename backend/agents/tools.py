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
    if not pinecone_index:
        return
    try:
        stats = pinecone_index.describe_index_stats()
        if stats.total_vector_count == 0:
            from razorpay_service import items
            for item in items.list_items(count=100).get("items", []):
                desc = item.get("description", "")
                index_product(item["id"], f"{item['name']} {desc}", {
                    "name": item["name"], "description": desc,
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
                    results.append({
                        "name": item["name"], "id": item["id"],
                        "price": item["amount"] / 100, "currency": item["currency"],
                        "description": item.get("description", ""), "category": "General",
                        "in_stock": item.get("active", True)
                    })
                if len(results) >= 5:
                    break
        except Exception as exc:
            logger.error("Catalog fallback failed: %s", exc)
    if not results:
        return "No products found matching your search."
    return "\n\n".join(
        f"- {p['name']} (ID: {p['id']})\n"
        f"  Price: {p['currency']} {p['price']}\n"
        f"  Category: {p.get('category', 'General')}\n"
        f"  Description: {p.get('description', '')}\n"
        f"  In Stock: {'Yes' if p.get('in_stock', True) else 'No'}"
        for p in results
    )


@tool
def get_product_details(item_id: str):
    """Get full details for a catalog product."""
    try:
        from razorpay_service import items
        item = items.fetch_item(item_id)
        return (
            f"Product: {item['name']}\nPrice: Rs.{item['amount']/100:,.2f}\n"
            f"Description: {item.get('description', 'N/A')}\nProduct ID: {item['id']}\n"
            f"Status: {'Available' if item.get('active', True) else 'Unavailable'}"
        )
    except Exception as exc:
        return f"Error fetching product details: {exc}"


@tool
def stage_purchase_intent(product_id: str, amount_paise: int) -> str:
    """Stage a product for checkout. This never authorizes payment."""
    return f"Purchase intent staged for {product_id} at a provisional amount of {amount_paise} paise. Await explicit confirmation."


@tool
def fetch_recommendations(
    state: Annotated[dict, InjectedState],
    customer_id: str = None,
    category: str = None,
) -> str:
    """Return evidence-backed cross-sell recommendations and record their lifecycle."""
    ctx = state.get("purchase_context", {})
    basket = ctx.get("basket_items", [])
    if not basket or not supabase:
        return "No data-backed recommendations are currently available."
    product_id = basket[0]["product_id"]
    try:
        res = (supabase.table("product_affinity")
               .select("*")
               .eq("product_id", product_id)
               .order("lift_score", desc=True).limit(5).execute())
        candidates = []
        for row in res.data or []:
            p = (supabase.table("products").select("product_id,name,price_paise,description,inventory_qty,active,category")
                 .eq("product_id", row["related_product_id"]).eq("merchant_id", "merchant_mxx_001").maybe_single().execute())
            if not p.data or not p.data.get("active") or (p.data.get("inventory_qty") or 0) <= 0:
                continue
            if p.data["product_id"] == product_id:
                continue
            candidates.append((row, p.data))
        if not candidates:
            return "No sufficiently strong in-stock data-backed recommendation was found."
        lines = []
        for row, product in candidates[:2]:
            rec_id = f"rec_{uuid.uuid4().hex[:12]}"
            supabase.table("recommendation_events").insert({
                "recommendation_id": rec_id,
                "session_id": state.get("session_id"), "customer_id": customer_id or state.get("customer_id"),
                "merchant_id": "merchant_mxx_001", "source_product_id": product_id,
                "recommended_product_id": product["product_id"], "recommendation_type": "CROSS_SELL",
                "agent_name": "Booster", "score": row.get("lift_score", 0),
                "reason": f"Observed co-purchase affinity; lift={row.get('lift_score', 0)}",
                "shown_at": None, "status": "GENERATED"
            }).execute()
            lines.append(f"- {product['name']} (Rs.{product['price_paise']/100:,.2f}) [Rec ID: {rec_id}] — evidence lift {row.get('lift_score', 0):.3f}")
        return "Data-backed recommendations:\n" + "\n".join(lines)
    except Exception as exc:
        logger.exception("Recommendation query failed")
        return f"Recommendation service unavailable: {exc}"


@tool
def analyze_campaign_opportunities() -> str:
    """Find merchant growth opportunities from persisted customer metrics."""
    if not supabase:
        return "Database connection not available."
    try:
        res = (supabase.table("customer_metrics")
               .select("customer_id,segment,lifetime_value_paise,churn_probability,preferred_category")
               .order("lifetime_value_paise", desc=True).limit(10).execute())
        if not res.data:
            return "No campaign opportunities found."
        lines = ["Detected high-value/churn opportunities:"]
        for c in res.data:
            lines.append(
                f"- {c['customer_id']} | segment={c.get('segment')} | "
                f"LTV=Rs.{(c.get('lifetime_value_paise') or 0)/100:,.2f} | "
                f"churn={c.get('churn_probability', 0):.2f} | category={c.get('preferred_category')}"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Error analyzing campaign opportunities: {exc}"


@tool
def create_razorpay_order(
    state: Annotated[dict, InjectedState],
    customer_email: Optional[str] = None,
    customer_contact: Optional[str] = None,
):
    """Create a Razorpay order only after deterministic Guardian validation of a persisted purchase intent."""
    if not supabase:
        return "Order blocked: Supabase is unavailable."
    ctx = state.get("purchase_context") or {}
    intent_id = ctx.get("purchase_intent_id")
    if not intent_id:
        return "Order blocked: missing purchase_intent_id."
    try:
        intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).maybe_single().execute()
        if not intent.data:
            return "Order blocked: purchase intent not found."
        intent = intent.data
        if intent.get("purchase_state") != "USER_CONFIRMED" or not intent.get("user_confirmed"):
            return "Order blocked by Guardian: explicit confirmation is required."
        basket = intent.get("basket") or []
        if not basket:
            return "Order blocked: empty basket."
        subtotal = 0
        validated_items = []
        for entry in basket:
            product_id, qty = entry["product_id"], int(entry.get("quantity", 1))
            product = (supabase.table("products").select("*").eq("product_id", product_id)
                       .eq("merchant_id", "merchant_mxx_001").maybe_single().execute())
            if not product.data or not product.data.get("active") or (product.data.get("inventory_qty") or 0) < qty:
                return "Order blocked by Guardian: product unavailable or insufficient inventory."
            unit = int(product.data["price_paise"])
            line = unit * qty
            subtotal += line
            validated_items.append((product.data, qty, unit, line))
        discount = int(intent.get("discount_paise") or 0)
        tax = int(intent.get("tax_paise") or 0)
        total = subtotal - discount + tax
        if total <= 0:
            return "Order blocked: invalid total."
        if int(intent.get("amount_paise") or 0) != total:
            return "Order blocked by Guardian: persisted amount does not match server-calculated basket total."
        # Idempotency: one local order per purchase intent.
        existing = supabase.table("orders").select("order_id").eq("purchase_intent_id", intent_id).limit(1).execute()
        if existing.data:
            return f"Order already exists for purchase intent {intent_id}: {existing.data[0]['order_id']}"
        validate_action(
            agent_name="Closer", action_type="create_razorpay_order",
            action_intent={"purchase_intent_id": intent_id, "user_confirmed": True,
                           "purchase_state": "USER_CONFIRMED", "action_type": "create_razorpay_order"},
            amount_paise=total
        )
        from razorpay_service import orders
        notes = {"purchase_intent_id": intent_id, "merchant_id": "merchant_mxx_001"}
        if customer_email: notes["customer_email"] = customer_email
        if customer_contact: notes["customer_contact"] = customer_contact
        rzp_order = orders.create_order(total, "INR", receipt=intent_id, notes=notes)
        local_order_id = f"ord_{uuid.uuid4().hex[:12]}"
        supabase.table("orders").insert({
            "order_id": local_order_id, "merchant_id": "merchant_mxx_001", "customer_id": intent.get("customer_id"),
            "status": "CREATED", "subtotal_paise": subtotal, "discount_paise": discount,
            "tax_paise": tax, "total_paise": total, "currency": "INR", "source": "AI_AGENT",
            "purchase_state": "ORDER_CREATED"
        }).execute()
        for product, qty, unit, line in validated_items:
            supabase.table("order_items").insert({
                "order_item_id": f"oi_{uuid.uuid4().hex[:12]}", "order_id": local_order_id,
                "product_id": product["product_id"], "quantity": qty, "unit_price_paise": unit,
                "discount_paise": 0, "total_paise": line
            }).execute()
        supabase.table("entity_mapping").insert({
            "synthetic_id": local_order_id, "entity_type": "order", "razorpay_id": rzp_order["id"]
        }).execute()
        supabase.table("purchase_intents").update({
            "purchase_state": "PAYMENT_PENDING", "razorpay_order_id": rzp_order["id"]
        }).eq("purchase_intent_id", intent_id).execute()
        return (
            f"Razorpay Order created successfully. Order ID: {rzp_order['id']}\n"
            f"Amount: Rs.{total/100:,.2f}\nLocal order: {local_order_id}\n"
            "Payment is pending; verify the Razorpay status before treating it as successful."
        )
    except GuardianException as exc:
        return f"Order blocked by Guardian: {exc}"
    except Exception as exc:
        logger.exception("Razorpay order creation failed")
        return f"Error creating order: {exc}"


@tool
def check_payment_status(state: Annotated[dict, InjectedState]) -> str:
    """Inspect the authoritative Razorpay order/payment state; never retries a payment."""
    ctx = state.get("purchase_context") or {}
    intent_id = ctx.get("purchase_intent_id")
    if not intent_id or not supabase:
        return "Unable to inspect payment state."
    try:
        intent = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", intent_id).maybe_single().execute()
        if not intent.data or not intent.data.get("razorpay_order_id"):
            return "No Razorpay order exists for this purchase intent."
        from razorpay_service import orders
        rzp_order_id = intent.data["razorpay_order_id"]
        rzp_order = orders.fetch_order(rzp_order_id)
        payments = orders.fetch_order_payments(rzp_order_id).get("items", [])
        if any(p.get("status") == "captured" for p in payments):
            return f"PAYMENT_SUCCESS: Razorpay order {rzp_order_id} has a captured payment."
        if payments and all(p.get("status") == "failed" for p in payments):
            return f"PAYMENT_FAILED: Razorpay order {rzp_order_id} has only failed payments. Do not retry this intent."
        return f"PAYMENT_UNKNOWN: Razorpay order {rzp_order_id} is {rzp_order.get('status', 'unknown')}; inspect before any recovery."
    except Exception as exc:
        return f"PAYMENT_UNKNOWN: unable to verify Razorpay state safely ({exc})."


@tool
def reset_purchase_intent(state: Annotated[dict, InjectedState]) -> str:
    """Create a fresh purchase intent only after a failed/unknown payment has been inspected."""
    if not supabase:
        return "Unable to reset purchase intent."
    ctx = state.get("purchase_context") or {}
    old_id = ctx.get("purchase_intent_id")
    if not old_id:
        return "No purchase intent to reset."
    try:
        old = supabase.table("purchase_intents").select("*").eq("purchase_intent_id", old_id).maybe_single().execute()
        if not old.data or old.data.get("purchase_state") not in ("PAYMENT_FAILED", "PAYMENT_UNKNOWN", "RECOVERY_PENDING"):
            return "Reset blocked: payment state has not been resolved."
        new_id = f"pi_{uuid.uuid4().hex[:12]}"
        new = dict(old.data)
        new["purchase_intent_id"] = new_id
        new["purchase_state"] = "PURCHASE_PENDING"
        new["user_confirmed"] = False
        new["razorpay_order_id"] = None
        new["razorpay_payment_id"] = None
        supabase.table("purchase_intents").insert({k: new[k] for k in (
            "purchase_intent_id","conversation_id","customer_id","merchant_id","purchase_state","basket",
            "subtotal_paise","discount_paise","tax_paise","amount_paise","user_confirmed","razorpay_order_id","razorpay_payment_id"
        )}).execute()
        return f"Fresh purchase intent created: {new_id}. Explicit confirmation is required again."
    except Exception as exc:
        return f"Unable to reset purchase intent: {exc}"


DISCOVERY_TOOLS = [search_catalog, get_product_details, fetch_recommendations, analyze_campaign_opportunities, stage_purchase_intent]
SCOUT_TOOLS = [search_catalog, get_product_details, stage_purchase_intent]
BOOSTER_TOOLS = [fetch_recommendations]
CAMPAIGNER_TOOLS = [analyze_campaign_opportunities]
PAYMENT_TOOLS = [create_razorpay_order, check_payment_status, reset_purchase_intent]
ALL_TOOLS = SCOUT_TOOLS + BOOSTER_TOOLS + CAMPAIGNER_TOOLS + PAYMENT_TOOLS
