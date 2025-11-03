"""
Cycle state tracking model for 90-day trading cycles.
Tracks detailed cycle metrics, phases, and performance.
"""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, Integer, Numeric, TIMESTAMP, Date, Boolean
from sqlalchemy.sql import func
from src.models.base import Base

class CycleState(Base):
    """Detailed state tracking for 90-day trading cycles."""
    __tablename__ = 'cycle_states'
    
    id = Column(Integer, primary_key=True)
    cycle_id = Column(String(32), nullable=False, index=True)
    cycle_day = Column(Integer, nullable=False)  # 1-90
    phase = Column(String(20), nullable=False)  # LOAD, ACTIVE, SCALE_OUT, FORCE_CLOSE
    
    # Capital tracking
    starting_capital = Column(Numeric, default=Decimal('0.00'))
    current_equity = Column(Numeric, default=Decimal('0.00'))
    realized_pnl = Column(Numeric, default=Decimal('0.00'))
    unrealized_pnl = Column(Numeric, default=Decimal('0.00'))
    
    # Risk metrics
    max_drawdown = Column(Numeric, default=Decimal('0.00'))
    high_water_mark = Column(Numeric, default=Decimal('0.00'))
    current_drawdown = Column(Numeric, default=Decimal('0.00'))
    
    # Position tracking
    positions_opened = Column(Integer, default=0)
    positions_closed = Column(Integer, default=0)
    positions_forced_closed = Column(Integer, default=0)
    
    # Performance metrics
    win_rate = Column(Numeric, default=Decimal('0.00'))
    avg_winner = Column(Numeric, default=Decimal('0.00'))
    avg_loser = Column(Numeric, default=Decimal('0.00'))
    expectancy = Column(Numeric, default=Decimal('0.00'))
    sharpe_ratio = Column(Numeric, default=Decimal('0.00'))
    
    # Risk gates
    drawdown_gate_status = Column(String(10), default='GREEN')  # GREEN, YELLOW, RED, NUCLEAR
    
    # Cash management
    cash_reserve_target = Column(Numeric, default=Decimal('0.10'))  # 10% reserve
    cash_reserve_actual = Column(Numeric, default=Decimal('0.00'))
    
    # Cycle validity
    is_valid_cycle = Column(Boolean, default=True)
    validity_reason = Column(String(255), default='')
    
    # Audit
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<CycleState(cycle_id='{self.cycle_id}', day={self.cycle_day}, phase='{self.phase}')>"
    
    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in cycle."""
        return max(0, 90 - self.cycle_day)
    
    @property
    def phase_progress(self) -> float:
        """Calculate phase progress as percentage."""
        if self.phase == 'LOAD':
            return min(100.0, (self.cycle_day / 7) * 100)
        elif self.phase == 'ACTIVE':
            return min(100.0, ((self.cycle_day - 7) / 53) * 100)
        elif self.phase == 'SCALE_OUT':
            return min(100.0, ((self.cycle_day - 60) / 15) * 100)
        elif self.phase == 'FORCE_CLOSE':
            return min(100.0, ((self.cycle_day - 75) / 15) * 100)
        return 0.0
    
    @property
    def total_return_pct(self) -> float:
        """Calculate total return percentage."""
        if self.starting_capital and self.starting_capital > 0:
            return float((self.current_equity - self.starting_capital) / self.starting_capital * 100)
        return 0.0
    
    @property
    def is_at_risk(self) -> bool:
        """Check if cycle is at risk based on drawdown gates."""
        return self.drawdown_gate_status in ['YELLOW', 'RED', 'NUCLEAR']
