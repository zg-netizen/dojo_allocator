"""Philosophy state tracking model."""
from sqlalchemy import Column, Date, Integer, Numeric, JSON, TIMESTAMP
from sqlalchemy.sql import func
from src.models.base import Base

class PhilosophyState(Base):
    """
    Daily philosophy adherence tracking.
    """
    __tablename__ = 'philosophy_state'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True)
    
    # Dalio metrics
    decisions_logged = Column(Integer, default=0)
    intuition_overrides = Column(Integer, default=0)
    
    # Buffett metrics
    trades_with_safety = Column(Numeric, default=0)
    trades_without_safety = Column(Numeric, default=0)
    
    # Pabrai metrics
    cluster_signals_detected = Column(Integer, default=0)
    cluster_positions_taken = Column(Integer, default=0)
    
    # O'Leary metrics
    positions_retired = Column(Integer, default=0)
    avg_return_per_cycle = Column(Numeric)
    
    # Saylor metrics
    positions_extended = Column(Integer, default=0)
    avg_sharpe_at_extension = Column(Numeric)
    
    # Japanese discipline metrics
    rule_violations = Column(Integer, default=0)
    violated_rules = Column(JSON)
    current_allocation_power = Column(Numeric, default=1.0)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
