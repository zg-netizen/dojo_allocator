"""
Scenario tracking models for parallel execution.
Each scenario runs independently with its own positions and P&L.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from src.models.base import Base


class Scenario(Base):
    """
    Tracks individual trading scenarios running in parallel.
    Each scenario has its own philosophy settings and performance metrics.
    """
    __tablename__ = 'scenarios'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Scenario identification
    scenario_name = Column(String(50), nullable=False, unique=True, index=True)
    scenario_type = Column(String(20), nullable=False)  # Conservative, Balanced, etc.
    
    # Philosophy settings (stored as JSON)
    philosophy_settings = Column(JSON, nullable=False)
    
    # Performance tracking
    initial_capital = Column(Float, nullable=False, default=100000.0)
    current_capital = Column(Float, nullable=False, default=100000.0)
    total_pnl = Column(Float, nullable=False, default=0.0)
    total_return_pct = Column(Float, nullable=False, default=0.0)
    
    # Trading statistics
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float, nullable=False, default=0.0)
    
    # Risk metrics
    max_drawdown = Column(Float, nullable=False, default=0.0)
    sharpe_ratio = Column(Float, nullable=False, default=0.0)
    volatility = Column(Float, nullable=False, default=0.0)
    
    # Status and timing
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    positions = relationship("ScenarioPosition", back_populates="scenario", cascade="all, delete-orphan")
    trades = relationship("ScenarioTrade", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioPosition(Base):
    """
    Positions specific to each scenario.
    Isolated from the main position tracking.
    """
    __tablename__ = 'scenario_positions'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Foreign key to scenario
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False, index=True)
    
    # Position details
    position_id = Column(String(100), nullable=False, unique=True, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # LONG, SHORT
    
    # Entry details
    entry_date = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    entry_value = Column(Float, nullable=False)
    
    # Exit details (if closed)
    exit_date = Column(DateTime)
    exit_price = Column(Float)
    exit_value = Column(Float)
    realized_pnl = Column(Float, default=0.0)
    
    # Position metadata
    conviction_tier = Column(String(1), nullable=False)  # S, A, B, C
    status = Column(String(20), nullable=False, default='OPEN')  # OPEN, CLOSED
    exit_reason = Column(String(50))  # PROFIT_TAKE, STOP_LOSS, EXPIRED, etc.
    
    # Risk management
    stop_loss = Column(Float)
    take_profit = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    scenario = relationship("Scenario", back_populates="positions")


class ScenarioTrade(Base):
    """
    Individual trades within each scenario for detailed tracking.
    """
    __tablename__ = 'scenario_trades'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Foreign key to scenario
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False, index=True)
    
    # Trade identification
    trade_id = Column(String(100), nullable=False, unique=True, index=True)
    position_id = Column(String(100), nullable=False, index=True)
    
    # Trade details
    symbol = Column(String(10), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # LONG, SHORT
    action = Column(String(10), nullable=False)  # BUY, SELL
    
    # Execution details
    execution_date = Column(DateTime, nullable=False)
    price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)
    
    # Fees and slippage
    commission = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    scenario = relationship("Scenario", back_populates="trades")
