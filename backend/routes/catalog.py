from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from razorpay_service import items

router = APIRouter(prefix="/catalog", tags=["catalog"])

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float # in INR
    category: Optional[str] = None
    image_url: Optional[str] = None

class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    amount: int # in paise
    currency: str
    active: bool

@router.get("/", response_model=List[ProductResponse])
async def list_catalog():
    """Lists all products from Razorpay Items API"""
    try:
        response = items.list_items()
        return response.get('items', [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{item_id}", response_model=ProductResponse)
async def get_catalog_item(item_id: str):
    """Gets a specific product from Razorpay Items API"""
    try:
        return items.fetch_item(item_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Item not found: {str(e)}")

@router.post("/", response_model=ProductResponse)
async def create_catalog_item(product: ProductCreate):
    """Creates a new product in the Razorpay Catalog"""
    try:
        amount_paise = int(product.price * 100)
        return items.create_item(product.name, product.description, amount_paise)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
