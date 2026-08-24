from .client import rzp
import logging

logger = logging.getLogger(__name__)

def create_order(amount_paise: int, currency: str = "INR", receipt: str = None, notes: dict = None):
    """Creates an order in Razorpay (Required before any payment)"""
    try:
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt,
            "notes": notes or {}
        }
        return rzp.order.create(payload)
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
        raise

def fetch_order(order_id: str):
    """Fetches a specific order"""
    try:
        return rzp.order.fetch(order_id)
    except Exception as e:
        logger.error(f"Error fetching order {order_id}: {e}")
        raise

def list_orders(count: int = 10, skip: int = 0):
    """Lists recent orders"""
    try:
        return rzp.order.all({"count": count, "skip": skip})
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        raise

def fetch_order_payments(order_id: str):
    """Fetches all payments associated with an order"""
    try:
        return rzp.order.payments(order_id)
    except Exception as e:
        logger.error(f"Error fetching payments for order {order_id}: {e}")
        raise
