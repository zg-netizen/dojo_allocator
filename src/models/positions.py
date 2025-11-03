"""Position database model."""
from sqlalchemy import Column, String, Numeric, TIMESTAMP, Integer, Boolean, ARRAY
from sqlalchemy.sql import func
from src.models.base import Base

class Position(Base):
    """
    Trading positions (both open and closed).
    """
    __tablename__ = 'positions'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    position_id = Column(String(64), unique=True, nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    direction = Column(String(4), nullable=False)
    
    # Entry details
    entry_date = Column(TIMESTAMP, nullable=False)
    entry_price = Column(Numeric)
    shares = Column(Numeric, nullable=False)
    entry_value = Column(Numeric)
    
    # Philosophy mapping
    source_signals = Column(ARRAY(String))
    conviction_tier = Column(String(10))
    philosophy_applied = Column(String(50))
    
    # Cycle management
    cycle_id = Column(String(32), index=True)
    
    # Exit details
    exit_date = Column(TIMESTAMP)
    exit_price = Column(Numeric)
    exit_value = Column(Numeric)
    realized_pnl = Column(Numeric)
    return_pct = Column(Numeric)
    
    # Round discipline
    round_start = Column(TIMESTAMP, nullable=False)
    round_expiry = Column(TIMESTAMP, nullable=False)
    round_extended = Column(Boolean, default=False)
    discipline_violations = Column(Integer, default=0)
    
    # State
    status = Column(String(20), default='OPEN', index=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
