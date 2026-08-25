from langchain_core.tools import tool
from razorpay_service import items, orders, payment_links
from agents.guardian import validate_action, GuardianException
import logging

logger = logging.getLogger(__name__)

@tool
def search_catalog(query: str, limit: int = 5):
    """Search the merchant's product catalog for items matching a query."""
    try:
        all_items = items.list_items(count=100).get('items', [])
        results = []
        q = query.lower()
        for item in all_items:
            if q in item.get('name', '').lower() or q in item.get('description', '').lower():
                price = item['amount'] / 100
                results.append(
                    f"Product: {item['name']}\n"
                    f"  Price: Rs.{price:,.2f}\n"
                    f"  Description: {item.get('description', 'N/A')}\n"
                    f"  Product ID: {item['id']}"
                )
            if len(results) >= limit:
                break
        return "\n---\n".join(results) if results else "No matching products found in our catalog."
    except Exception as e:
        return f"Error searching catalog: {str(e)}"

@tool
def get_product_details(item_id: str):
    """Get full details of a specific product by its ID."""
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
DISCOVERY_TOOLS = [search_catalog, get_product_details]

# Payment tools (for Closer)
PAYMENT_TOOLS = [create_payment_link_for_product]

# All tools combined (for ToolNode execution)
ALL_TOOLS = [search_catalog, get_product_details, create_payment_link_for_product]
