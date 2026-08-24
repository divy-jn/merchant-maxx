import razorpay
from config import settings
import logging

logger = logging.getLogger(__name__)

class RazorpayClient:
    def __init__(self):
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            logger.warning("Razorpay credentials not fully configured!")
            
        self.client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        # Optional: set app details for telemetry/tracking if needed
        # self.client.set_app_details({"title" : "Merchant Maxx", "version" : "1.0.0"})

    def get_client(self):
        return self.client

rzp = RazorpayClient().get_client()
