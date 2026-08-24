from langchain_core.tools import tool
from razorpay_service import items, orders, payment_links
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
                results.append(f"ID: {item['id']} | Name: {item['name']} | Price: ₹{item['amount']/100}")
            if len(results) >= limit:
                break
        return "\n".join(results) if results else "No items found."
    except Exception as e:
        return f"Error searching catalog: {str(e)}"

@tool
def get_product_details(item_id: str):
    """Get full details of a specific product by its ID."""
    try:
        item = items.fetch_item(item_id)
        return f"ID: {item['id']}\nName: {item['name']}\nDescription: {item.get('description', '')}\nPrice: ₹{item['amount']/100}"
    except Exception as e:
        return f"Error fetching product details: {str(e)}"

@tool
def create_payment_link_for_product(item_id: str, customer_email: str = None, customer_contact: str = None):
    """Generates a payment link to purchase a specific product."""
    try:
        item = items.fetch_item(item_id)
        customer = {}
        if customer_email: customer["email"] = customer_email
        if customer_contact: customer["contact"] = customer_contact
        
        plink = payment_links.create_payment_link(
            amount_paise=item["amount"],
            description=f"Purchase of {item['name']}",
            customer=customer if customer else None
        )
        return f"Payment Link Created Successfully!\nLink: {plink['short_url']}\nAmount: ₹{plink['amount']/100}"
    except Exception as e:
        return f"Error creating payment link: {str(e)}"

# A combined list of all tools
ALL_TOOLS = [search_catalog, get_product_details, create_payment_link_for_product]
