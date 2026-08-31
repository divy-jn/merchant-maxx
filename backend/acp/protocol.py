from fastapi import APIRouter
from .schemas import AgentCommerceDiscovery, AgentCapability
from config import settings

router = APIRouter(tags=["acp"])

@router.get("/.well-known/agent-commerce.json", response_model=AgentCommerceDiscovery)
async def get_acp_discovery():
    """Service discovery endpoint for AI Agents to understand merchant capabilities"""
    return AgentCommerceDiscovery(
        merchant_name="Merchant Maxx (Demo)",
        capabilities=[
            AgentCapability(
                name="catalog_search",
                description="Search the merchant's catalog for products.",
                endpoint="/acp/catalog/search",
                method="POST"
            )
        ]
    )
