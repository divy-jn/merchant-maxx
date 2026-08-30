import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from razorpay_service import items
from config import settings
import logging
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock catalog data
DEMO_PRODUCTS = [
    {"name": "Wireless Noise-Cancelling Headphones", "description": "Premium over-ear headphones with 30h battery life.", "price": 14999.00, "category": "Audio"},
    {"name": "Smart Watch Pro", "description": "Fitness tracker with heart rate monitor and GPS.", "price": 8999.00, "category": "Wearables"},
    {"name": "Ultra-Fast 65W Charger", "description": "GaN charger for laptops and phones.", "price": 1999.00, "category": "Accessories"},
    {"name": "Mechanical Gaming Keyboard", "description": "RGB backlit keyboard with tactile switches.", "price": 5499.00, "category": "Peripherals"},
    {"name": "4K Web Camera", "description": "Ultra HD webcam with built-in noise reducing microphone.", "price": 4299.00, "category": "Accessories"},
    {"name": "Portable SSD 1TB", "description": "High-speed external solid state drive.", "price": 7999.00, "category": "Storage"},
    {"name": "Ergonomic Wireless Mouse", "description": "Comfortable mouse with customizable buttons.", "price": 2499.00, "category": "Peripherals"},
    {"name": "Bluetooth Speaker Splashproof", "description": "Portable speaker with deep bass.", "price": 3499.00, "category": "Audio"},
    {"name": "Laptop Stand Aluminum", "description": "Adjustable stand for better ergonomics.", "price": 1299.00, "category": "Accessories"},
    {"name": "USB-C Hub 7-in-1", "description": "Multiport adapter with HDMI, USB 3.0, and SD card reader.", "price": 2999.00, "category": "Accessories"},
]

def seed_products():
    logger.info("Starting product seeding...")
    
    # Initialize Supabase client
    supabase: Client = None
    if settings.SUPABASE_URL and settings.supabase_active_key:
        try:
            supabase = create_client(settings.SUPABASE_URL, settings.supabase_active_key)
            logger.info("Supabase client initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")
            
    for prod in DEMO_PRODUCTS:
        try:
            amount_paise = int(prod["price"] * 100)
            logger.info(f"Creating item in Razorpay: {prod['name']}")
            rzp_item = items.create_item(prod["name"], prod["description"], amount_paise)
            
            logger.info(f"Success! Razorpay ID: {rzp_item['id']}")
            
            # Sync to Supabase if available
            if supabase:
                try:
                    db_payload = {
                        "razorpay_item_id": rzp_item['id'],
                        "name": prod["name"],
                        "description": prod["description"],
                        "amount": amount_paise,
                        "currency": "INR",
                        "category": prod["category"],
                        "active": True
                    }
                    supabase.table("products").insert(db_payload).execute()
                    logger.info(f"Synced {prod['name']} to Supabase")
                except Exception as e:
                    logger.error(f"Failed to sync {prod['name']} to Supabase: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to create item {prod['name']}: {e}")

    logger.info("Product seeding completed!")

if __name__ == "__main__":
    seed_products()
