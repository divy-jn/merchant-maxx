from .client import rzp
import logging

logger = logging.getLogger(__name__)

def issue_refund(payment_id: str, amount_paise: int = None, speed: str = "normal", notes: dict = None, receipt: str = None):
    """Issues a full or partial refund for a captured payment"""
    try:
        payload = {}
        if amount_paise: payload["amount"] = amount_paise
        if speed: payload["speed"] = speed
        if notes: payload["notes"] = notes
        if receipt: payload["receipt"] = receipt
        
        return rzp.payment.refund(payment_id, payload)
    except Exception as e:
        logger.error(f"Error issuing refund for payment {payment_id}: {e}")
        raise

def fetch_refund(refund_id: str):
    """Fetches details of a specific refund"""
    try:
        return rzp.refund.fetch(refund_id)
    except Exception as e:
        logger.error(f"Error fetching refund {refund_id}: {e}")
        raise

def fetch_payment_refunds(payment_id: str):
    """Fetches all refunds associated with a payment"""
    try:
        return rzp.payment.refunds(payment_id)
    except Exception as e:
        logger.error(f"Error fetching refunds for payment {payment_id}: {e}")
        raise
