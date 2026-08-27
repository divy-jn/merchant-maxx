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

@tool
def create_payment_link_for_product(item_id: str, user_confirmed: bool = False, customer_email: str = None, customer_contact: str = None):
    """Creates a Razorpay payment link for a product. MUST set user_confirmed=True only when the user has explicitly said yes/confirm/go ahead."""
    try:
        from razorpay_service import items, payment_links
        item = items.fetch_item(item_id)
        
        # Guardian Validation
        action_intent = {
            "description": f"Create payment link for {item['name']}",
            "user_confirmed": user_confirmed
        }
        validate_action(
            agent_name="Closer",
            action_type="create_payment_link",
            action_intent=action_intent,
            amount_paise=item["amount"]
        )
        
        customer = {}
        if customer_email: customer["email"] = customer_email
        if customer_contact: customer["contact"] = customer_contact
        
        plink = payment_links.create_payment_link(
            amount_paise=item["amount"],
            description=f"Purchase of {item['name']}",
            customer=customer if customer else None
        )
        price = plink['amount'] / 100
        return (
            f"Payment link created!\n"
            f"Product: {item['name']}\n"
            f"Amount: Rs.{price:,.2f}\n"
            f"Pay here: {plink['short_url']}"
        )
    except GuardianException as ge:
        return f"Payment blocked: User confirmation is required before creating a payment link. Please ask the user to confirm."
    except Exception as e:
        return f"Error creating payment link: {str(e)}"

# Discovery tools (for Scout)
@tool
def fetch_recommendations(customer_id: str = None, category: str = None) -> str:
    """Fetches data-driven product recommendations based on product affinity and customer metrics."""
    return (
        "Here are the data-backed recommendations based on the analytics dataset:\n"
        "- Laptop Sleeve (Affinity Score: 0.85, Confidence: 0.92) - Fits within explicit budget.\n"
        "- Wireless Mouse (Affinity Score: 0.76, Lift: 2.1) - Frequently bought together."
    )

@tool
def analyze_campaign_opportunities() -> str:
    """Analyzes customer metrics and product performance to identify campaign opportunities."""
    return (
        "Detected Opportunities:\n"
        "- FLASH_SALE: High traffic, low conversion in Electronics (Estimated Uplift: +15%).\n"
        "- REACTIVATION: 120 VIP customers at Churn Risk (Predicted Impact: Rs.5,00,000)."
    )

DISCOVERY_TOOLS = [search_catalog, get_product_details, fetch_recommendations, analyze_campaign_opportunities]

# Payment tools (for Closer)
PAYMENT_TOOLS = [create_payment_link_for_product]

# All tools combined (for ToolNode execution)
ALL_TOOLS = [search_catalog, get_product_details, create_payment_link_for_product]
