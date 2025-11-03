"""
Order management endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from src.models.base import get_db
from src.models.orders import Order

router = APIRouter()

class OrderResponse(BaseModel):
    order_id: str
    position_id: str
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    status: str
    filled_qty: Optional[Decimal]
    filled_avg_price: Optional[Decimal]
    created_at: datetime
    filled_at: Optional[datetime]
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[OrderResponse])
def list_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    List orders with optional filters.
    """
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.status == status.upper())
    if symbol:
        query = query.filter(Order.symbol == symbol.upper())
    
    orders = query.order_by(desc(Order.created_at)).limit(limit).all()
    return orders

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)):
    """
    Get specific order by ID.
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}, 404
    return order
