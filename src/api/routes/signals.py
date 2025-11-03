"""
Signal management endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from src.models.base import get_db
from src.models.signals import Signal

router = APIRouter()

class SignalResponse(BaseModel):
    signal_id: str
    symbol: str
    direction: str
    source: str
    conviction_tier: Optional[str]
    total_score: Optional[float]
    status: str
    discovered_at: datetime
    filer_name: Optional[str]
    transaction_value: Optional[float]
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[SignalResponse])
def list_signals(
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, EXPIRED, REJECTED)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    tier: Optional[str] = Query(None, description="Filter by conviction tier (S, A, B, C)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    List signals with optional filters.
    """
    query = db.query(Signal)
    
    if status:
        query = query.filter(Signal.status == status.upper())
    if symbol:
        query = query.filter(Signal.symbol == symbol.upper())
    if tier:
        query = query.filter(Signal.conviction_tier == tier.upper())
    
    signals = query.order_by(desc(Signal.discovered_at)).limit(limit).all()
    return signals

@router.get("/{signal_id}", response_model=SignalResponse)
def get_signal(signal_id: str, db: Session = Depends(get_db)):
    """
    Get specific signal by ID.
    """
    signal = db.query(Signal).filter(Signal.signal_id == signal_id).first()
    if not signal:
        return {"error": "Signal not found"}, 404
    return signal

@router.get("/stats/summary")
def signal_stats(db: Session = Depends(get_db)):
    """
    Get signal statistics summary.
    """
    total = db.query(Signal).count()
    active = db.query(Signal).filter(Signal.status == 'ACTIVE').count()
    rejected = db.query(Signal).filter(Signal.status == 'REJECTED').count()
    
    # Count by tier
    tier_s = db.query(Signal).filter(Signal.conviction_tier == 'S').count()
    tier_a = db.query(Signal).filter(Signal.conviction_tier == 'A').count()
    tier_b = db.query(Signal).filter(Signal.conviction_tier == 'B').count()
    tier_c = db.query(Signal).filter(Signal.conviction_tier == 'C').count()
    
    return {
        "total": total,
        "active": active,
        "rejected": rejected,
        "by_tier": {
            "S": tier_s,
            "A": tier_a,
            "B": tier_b,
            "C": tier_c
        }
    }
