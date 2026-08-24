from .client import rzp
import logging
import time

logger = logging.getLogger(__name__)

def create_payment_link(amount_paise: int, currency: str = "INR", description: str = "", customer: dict = None, expire_by: int = None):
    """Creates a standard payment link (Plink)"""
    try:
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "description": description,
        }
        
        if customer:
            payload["customer"] = customer
            
        if expire_by:
            payload["expire_by"] = expire_by
        else:
            # Default to 24 hours from now
            payload["expire_by"] = int(time.time()) + 86400
            
        return rzp.payment_link.create(payload)
    except Exception as e:
        logger.error(f"Error creating payment link: {e}")
        raise

def fetch_payment_link(plink_id: str):
    """Fetches a specific payment link"""
    try:
        return rzp.payment_link.fetch(plink_id)
    except Exception as e:
        logger.error(f"Error fetching payment link {plink_id}: {e}")
        raise
