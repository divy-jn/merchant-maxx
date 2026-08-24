from .client import rzp
import logging

logger = logging.getLogger(__name__)

def create_customer(name: str, email: str, contact: str, fail_existing: int = 0):
    """Creates a customer in Razorpay"""
    try:
        payload = {
            "name": name,
            "email": email,
            "contact": contact,
            "fail_existing": fail_existing
        }
        return rzp.customer.create(payload)
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise

def fetch_customer(customer_id: str):
    """Fetches a specific customer"""
    try:
        return rzp.customer.fetch(customer_id)
    except Exception as e:
        logger.error(f"Error fetching customer {customer_id}: {e}")
        raise

def update_customer(customer_id: str, name: str = None, email: str = None, contact: str = None):
    """Updates an existing customer"""
    try:
        payload = {}
        if name: payload["name"] = name
        if email: payload["email"] = email
        if contact: payload["contact"] = contact
        
        return rzp.customer.edit(customer_id, payload)
    except Exception as e:
        logger.error(f"Error updating customer {customer_id}: {e}")
        raise
