from typing import Any, Dict
from utils.supabase_client import supabase

def get_customer_context(customer_id: str) -> Dict[str, Any]:
    """Build a compact customer history context from Supabase."""
    if not supabase or not customer_id:
        return {"customer_id": customer_id, "history_available": False}

    metrics_q = supabase.table("customer_metrics").select("*").eq("customer_id", customer_id).maybe_single().execute()
    customer_q = supabase.table("customers").select("customer_id,name,city,state,segment").eq("customer_id", customer_id).maybe_single().execute()
    orders_q = (supabase.table("orders").select("order_id,total_paise,status,source,created_at")
                .eq("customer_id", customer_id).order("created_at", desc=True).limit(5).execute())
    events_q = (supabase.table("customer_events").select("event_type,product_id,created_at")
                .eq("customer_id", customer_id).order("created_at", desc=True).limit(20).execute())

    metrics = metrics_q.data or {}
    customer = customer_q.data or {}
    context = {
        "customer_id": customer_id,
        "name": customer.get("name"),
        "location": {"city": customer.get("city"), "state": customer.get("state")},
        "segment": metrics.get("segment") or customer.get("segment"),
        "preferred_category": metrics.get("preferred_category"),
        "lifetime_value_paise": metrics.get("lifetime_value_paise", 0),
        "avg_order_value_paise": metrics.get("avg_order_value_paise", 0),
        "churn_probability": metrics.get("churn_probability", 0),
        "purchase_probability": metrics.get("purchase_probability", 0),
        "recent_orders": orders_q.data or [],
        "recent_events": events_q.data or [],
        "history_available": True,
    }
    return context
