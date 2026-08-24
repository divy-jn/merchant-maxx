from .client import rzp
import logging

logger = logging.getLogger(__name__)

def fetch_payment(payment_id: str):
    """Fetches a specific payment"""
    try:
        return rzp.payment.fetch(payment_id)
    except Exception as e:
        logger.error(f"Error fetching payment {payment_id}: {e}")
        raise

def capture_payment(payment_id: str, amount_paise: int, currency: str = "INR"):
    """Captures an authorized payment (Requires the exact authorized amount)"""
    try:
        payload = {
            "amount": amount_paise,
            "currency": currency
        }
        return rzp.payment.capture(payment_id, amount_paise, payload)
    except Exception as e:
        logger.error(f"Error capturing payment {payment_id}: {e}")
        raise

def get_payment_details(payment_id: str):
    """Gets expanded payment details including card/upi info if available"""
    try:
        return rzp.payment.fetch(payment_id, {"expand[]": "card"})
    except Exception as e:
        logger.error(f"Error getting payment details {payment_id}: {e}")
        raise
