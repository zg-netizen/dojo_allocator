"""
Position management endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from src.models.base import get_db
from src.models.positions import Position

router = APIRouter()

class PositionResponse(BaseModel):
    position_id: str
    symbol: str
    direction: str
    shares: Decimal
    entry_price: Optional[Decimal]
    exit_price: Optional[Decimal]
    realized_pnl: Optional[Decimal]
    return_pct: Optional[Decimal]
    status: str
    conviction_tier: str
    entry_date: datetime
    exit_date: Optional[datetime]
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[PositionResponse])
def list_positions(
    status: Optional[str] = Query(None, description="Filter by status (OPEN, CLOSED)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    List positions with optional filters.
    """
    query = db.query(Position)
    
    if status:
        query = query.filter(Position.status == status.upper())
    if symbol:
        query = query.filter(Position.symbol == symbol.upper())
    
    positions = query.order_by(desc(Position.entry_date)).limit(limit).all()
    return positions

@router.get("/{position_id}", response_model=PositionResponse)
def get_position(position_id: str, db: Session = Depends(get_db)):
    """
    Get specific position by ID.
    """
    position = db.query(Position).filter(Position.position_id == position_id).first()
    if not position:
        return {"error": "Position not found"}, 404
    return position

@router.get("/stats/summary")
def position_stats(db: Session = Depends(get_db)):
    """
    Get position statistics summary.
    """
    from sqlalchemy import func
    
    total = db.query(Position).count()
    open_count = db.query(Position).filter(Position.status == 'OPEN').count()
    closed_count = db.query(Position).filter(Position.status == 'CLOSED').count()
    
    # Total P&L
    total_pnl = db.query(func.sum(Position.realized_pnl)).filter(
        Position.status == 'CLOSED'
    ).scalar() or Decimal(0)
    
    # Win rate
    winners = db.query(Position).filter(
        Position.status == 'CLOSED',
        Position.realized_pnl > 0
    ).count()
    
    win_rate = (winners / closed_count * 100) if closed_count > 0 else 0
    
    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "total_pnl": float(total_pnl),
        "win_rate": round(win_rate, 2)
    }
