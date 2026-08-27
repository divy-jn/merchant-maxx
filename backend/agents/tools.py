from langchain_core.tools import tool
from search.vector_store import search_products_vector, pinecone_index, index_product
from cache.redis_client import cached
from agents.guardian import validate_action, GuardianException
import logging

logger = logging.getLogger(__name__)

# Setup: Index catalog if Pinecone is empty
def _ensure_catalog_indexed():
    if not pinecone_index:
        return
    try:
        stats = pinecone_index.describe_index_stats()
        if stats.total_vector_count == 0:
            print("Indexing catalog to Pinecone...")
            from razorpay_service import items
            all_items = items.list_items(count=100).get('items', [])
            for item in all_items:
                desc = item.get('description', '')
                price = item['amount'] / 100
                text = f"{item['name']} {desc}"
                metadata = {
                    "name": item['name'],
                    "description": desc,
                    "price": price,
                    "currency": item['currency'],
                    "in_stock": item.get('active', True),
                    "category": "General" # Razorpay items don't have categories by default
                }
                index_product(item['id'], text, metadata)
            print("Indexing complete.")
    except Exception as e:
        print(f"Error checking Pinecone index: {e}")

_ensure_catalog_indexed()

@tool
@cached(ttl=600)
def search_catalog(query: str, category: str = None) -> str:
    """
    Search the merchant's product catalog. Use this tool when a user asks about products, prices, or availability.
    Args:
        query: The search term (e.g., 'headphones', 'usb cable')
        category: Optional category filter (e.g., 'Electronics', 'Accessories')
    """
    # Try Pinecone semantic search first
    results = search_products_vector(query, top_k=3, category=category)
    
    # Fallback to keyword search via Razorpay Items API if vector search returns nothing
    if not results:
        try:
            from razorpay_service import items
            all_items = items.list_items(count=100).get('items', [])
            q = query.lower()
            for item in all_items:
                if q in item.get('name', '').lower() or q in item.get('description', '').lower():
                    results.append({
                        "name": item['name'],
                        "id": item['id'],
                        "price": item['amount'] / 100,
                        "currency": item['currency'],
                        "description": item.get('description', ''),
                        "category": "General",
                        "in_stock": item.get('active', True)
                    })
                if len(results) >= 3:
                    break
        except Exception as e:
            logger.error(f"Keyword search fallback failed: {e}")
    
    if not results:
        return "No products found matching your search."
        
    formatted_results = []
    for p in results:
        formatted_results.append(
            f"- {p['name']} (ID: {p['id']})\n"
            f"  Price: {p['currency']} {p['price']}\n"
            f"  Category: {p['category']}\n"
            f"  Description: {p['description']}\n"
            f"  In Stock: {'Yes' if p['in_stock'] else 'No'}"
        )
    return "\n\n".join(formatted_results)

@tool
def get_product_details(item_id: str):
    """Get full details of a specific product by its ID."""
    from razorpay_service import items
    try:
        item = items.fetch_item(item_id)
        price = item['amount'] / 100
        return (
            f"Product: {item['name']}\n"
            f"Price: Rs.{price:,.2f}\n"
            f"Description: {item.get('description', 'N/A')}\n"
            f"Product ID: {item['id']}\n"
            f"Status: {'Available' if item.get('active', True) else 'Unavailable'}"
        )
    except Exception as e:
        return f"Error fetching product details: {str(e)}"

from langgraph.prebuilt import InjectedState
from typing import Annotated

@tool
def create_razorpay_order(
    state: Annotated[dict, InjectedState], 
    customer_email: str = None, 
    customer_contact: str = None
):
    """Creates a Razorpay Order based on the user's current purchase context."""
    try:
        from razorpay_service import items, orders
        
        ctx = state.get("purchase_context", {})
        if not ctx or not ctx.get("basket_items"):
            return "Error: No product selected in purchase context."
            
        item_id = ctx["basket_items"][0]["product_id"]
        amount = ctx["amount_paise"]
        user_confirmed = state.get("user_confirmed", False)
        
        item = items.fetch_item(item_id)
        
        # Guardian Validation
        action_intent = {
            "description": f"Create order for {item['name']}",
            "user_confirmed": user_confirmed,
            "purchase_state": state.get("purchase_state", "IDLE"),
            "purchase_intent_id": ctx.get("purchase_intent_id"),
            "action_type": "create_razorpay_order"
        }
        validate_action(
            agent_name="Closer",
            action_type="create_razorpay_order",
            action_intent=action_intent,
            amount_paise=amount
        )
        
        notes = {}
        if customer_email: notes["customer_email"] = customer_email
        if customer_contact: notes["customer_contact"] = customer_contact
        notes["item_name"] = item["name"]
        
        order = orders.create_order(
            amount_paise=amount,
            currency="INR",
            receipt=ctx.get("purchase_intent_id"),
            notes=notes
        )
        
        try:
            from utils.supabase_client import supabase
            import uuid
            import logging
            logger = logging.getLogger(__name__)
            
            local_order_id = f"ord_{uuid.uuid4().hex[:12]}"
            if supabase:
                supabase.table("entity_mapping").insert({
                    "synthetic_id": local_order_id,
                    "entity_type": "order",
                    "razorpay_id": order["id"]
                }).execute()
        except Exception as e:
            logger.error(f"Failed to save entity mapping: {e}")

        price = order['amount'] / 100
        return (
            f"Razorpay Order created successfully!\n"
            f"Product: {item['name']}\n"
            f"Amount: Rs.{price:,.2f}\n"
            f"Order ID: {order['id']}\n"
            f"Tell the user: 'I have generated your order. Please proceed to payment using Order ID: {order['id']}'"
        )
    except GuardianException as ge:
        return f"Order blocked by Guardian: {str(ge)}"
    except Exception as e:
        return f"Error creating order: {str(e)}"

@tool
def confirm_and_pay() -> str:
    """Call this tool ONLY when the user has explicitly confirmed they want to proceed with the purchase."""
    return "Purchase confirmed by user. Please proceed to generate the order."

@tool
def reset_purchase_intent() -> str:
    """Call this tool ONLY if the previous payment failed or was unknown, and the user wants to try paying again."""
    return "Purchase intent reset. You may now generate a new order."

# Discovery tools (for Scout)
@tool
def fetch_recommendations(state: Annotated[dict, InjectedState], customer_id: str = None, category: str = None) -> str:
    """Fetches data-driven product recommendations based on product affinity and customer metrics."""
    ctx = state.get("purchase_context", {})
    basket = ctx.get("basket_items", [])
    if not basket:
        return "No products in basket to recommend against."
        
    product_id = basket[0]["product_id"]
    
    from utils.supabase_client import supabase
    if not supabase:
        return "Database connection not available. Unable to fetch data-backed recommendations."
        
    try:
        # Fetch affinity
        res = supabase.table("product_affinity").select("*, products(name, price_paise, description)").eq("product_id", product_id).order("lift_score", desc=True).limit(2).execute()
        
        if not res.data:
            return "No data-backed recommendations found for this product."
            
        recs = []
        import uuid
        for r in res.data:
            prod = r.get("products", {})
            name = prod.get("name") or r["related_product_id"]
            price = prod.get("price_paise", 0) / 100
            
            # Log generation to DB
            rec_id = f"rec_{uuid.uuid4().hex[:12]}"
            try:
                supabase.table("recommendation_events").insert({
                    "recommendation_id": rec_id,
                    "session_id": state.get("session_id"),
                    "customer_id": state.get("customer_id"),
                    "merchant_id": "merchant_mxx_001",
                    "source_product_id": product_id,
                    "recommended_product_id": r["related_product_id"],
                    "recommendation_type": "CROSS_SELL",
                    "agent_name": "Booster",
                    "score": r.get("lift_score", 0),
                    "reason": f"co_purchase (lift: {r.get('lift_score', 0)})",
                    "status": "GENERATED"
                }).execute()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to log recommendation_event: {e}")
                
            recs.append(f"- {name} (Rs.{price:,.2f}) [Rec ID: {rec_id}] - Affinity: {r.get('support_score', 0)}, Lift: {r.get('lift_score', 0)}")
            
        return "Data-backed recommendations:\n" + "\n".join(recs)
    except Exception as e:
        return f"Error fetching recommendations: {e}"

@tool
def analyze_campaign_opportunities() -> str:
    """Analyzes customer metrics and product performance to identify campaign opportunities."""
    from utils.supabase_client import supabase
    if not supabase:
        return "Database connection not available."
        
    try:
        # Simple campaign opportunity detection from customer_metrics
        res = supabase.table("customer_metrics").select("*").order("ltv", desc=True).limit(5).execute()
        if not res.data:
            return "No campaign opportunities found."
            
        opportunities = ["Detected Opportunities:"]
        opportunities.append("- HIGH_VALUE_VIP: Top customers ready for premium cross-sell.")
        for c in res.data:
            opportunities.append(f"  - Customer {c['customer_id']} (Segment: {c.get('segment', 'General')}, LTV: Rs.{c.get('ltv', 0):.2f})")
            
        return "\n".join(opportunities)
    except Exception as e:
        return f"Error analyzing campaign opportunities: {e}"

@tool
def stage_purchase_intent(product_id: str, amount_paise: int) -> str:
    """Stages a product for purchase checkout. Use this when the user explicitly wants to buy a product."""
    return f"Purchase intent staged for {product_id}."

DISCOVERY_TOOLS = [search_catalog, get_product_details, fetch_recommendations, analyze_campaign_opportunities, stage_purchase_intent]

# Payment tools (for Closer)
PAYMENT_TOOLS = [create_razorpay_order, confirm_and_pay, reset_purchase_intent]

# All tools combined (for ToolNode execution)
ALL_TOOLS = [search_catalog, get_product_details, create_razorpay_order, stage_purchase_intent, confirm_and_pay, reset_purchase_intent]
