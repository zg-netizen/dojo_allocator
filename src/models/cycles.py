"""
Cycle model for tracking trading cycles.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
from src.models.base import Base


class Cycle(Base):
    """
    Represents a trading cycle with fixed start/end dates.
    """
    __tablename__ = 'cycles'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Cycle identification
    cycle_id = Column(String(32), nullable=False, unique=True, index=True)
    
    # Cycle timing
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String(20), default='ACTIVE')  # ACTIVE, COMPLETED, CANCELLED
    
    # Position limits
    max_positions = Column(Integer, default=10)
    target_position_size = Column(Float, default=0.03)  # 3% of portfolio
    max_position_size = Column(Float, default=0.05)     # 5% of portfolio
    min_position_size = Column(Float, default=0.01)     # 1% of portfolio
    
    # Performance tracking
    total_invested = Column(Float, default=0.0)
    total_return = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    avg_winner = Column(Float, default=0.0)
    avg_loser = Column(Float, default=0.0)
    
    # Activity tracking
    positions_opened = Column(Integer, default=0)
    positions_closed = Column(Integer, default=0)
    signals_analyzed = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Cycle(cycle_id='{self.cycle_id}', status='{self.status}', start='{self.start_date.date()}', end='{self.end_date.date()}')>"
