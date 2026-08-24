from .client import rzp
import logging

logger = logging.getLogger(__name__)

def create_item(name: str, description: str, amount_paise: int, currency: str = "INR"):
    """Creates an item in the Razorpay Catalog"""
    try:
        payload = {
            "name": name,
            "description": description,
            "amount": amount_paise,
            "currency": currency
        }
        return rzp.item.create(payload)
    except Exception as e:
        logger.error(f"Error creating Razorpay item: {e}")
        raise

def fetch_item(item_id: str):
    """Fetches a specific item from Razorpay"""
    try:
        return rzp.item.fetch(item_id)
    except Exception as e:
        logger.error(f"Error fetching item {item_id}: {e}")
        raise

def list_items(count: int = 10, skip: int = 0):
    """Lists items from Razorpay"""
    try:
        return rzp.item.all({"count": count, "skip": skip})
    except Exception as e:
        logger.error(f"Error listing items: {e}")
        raise

def update_item(item_id: str, active: bool):
    """Updates an item (active/inactive)"""
    try:
        payload = {"active": active}
        return rzp.item.edit(item_id, payload)
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        raise

def delete_item(item_id: str):
    """Deletes an item from Razorpay"""
    try:
        return rzp.item.delete(item_id)
    except Exception as e:
        logger.error(f"Error deleting item {item_id}: {e}")
        raise
