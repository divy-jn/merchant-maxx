from fastapi import APIRouter, HTTPException
from .schemas import ProductQuery
from razorpay_service import items

router = APIRouter(prefix="/acp/catalog", tags=["acp-discovery"])

@router.post("/search")
async def search_catalog(query: ProductQuery):
    """
    Agent-facing endpoint to search the product catalog.
    In a real system, this would use pgvector or semantic search.
    For this demo, we'll do a simple text match against the Razorpay items.
    """
    try:
        all_items = items.list_items(count=100).get('items', [])
        results = []
        
        q = query.query.lower()
        
        for item in all_items:
            # Simple matching logic
            name_match = q in item.get('name', '').lower()
            desc_match = q in item.get('description', '').lower()
            
            if name_match or desc_match:
                # Apply price filters if any
                if query.min_price and item.get('amount', 0) < query.min_price:
                    continue
                if query.max_price and item.get('amount', 0) > query.max_price:
                    continue
                    
                results.append(item)
                
            if len(results) >= query.limit:
                break
                
        return {"results": results, "count": len(results)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
