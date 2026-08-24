from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class AgentCapability(BaseModel):
    name: str
    description: str
    endpoint: str
    method: str
    parameters: Optional[Dict[str, Any]] = None

class AgentCommerceDiscovery(BaseModel):
    version: str = "1.0.0"
    merchant_name: str
    capabilities: List[AgentCapability]

class ProductQuery(BaseModel):
    query: str
    category: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    limit: int = 10

class PurchaseIntent(BaseModel):
    product_id: str
    quantity: int = 1
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
