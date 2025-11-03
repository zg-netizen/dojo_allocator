"""Signal database model."""
from sqlalchemy import Column, String, Numeric, TIMESTAMP, Integer, JSON
from sqlalchemy.sql import func
from src.models.base import Base

class Signal(Base):
    """
    Trade signals from various sources (insider, congressional, 13F, options).
    """
    __tablename__ = 'signals'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    signal_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # Source information
    source = Column(String(32), nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    direction = Column(String(4), nullable=False)
    
    # Filer information
    filer_name = Column(String(255))
    filer_cik = Column(String(20))
    transaction_date = Column(TIMESTAMP)
    filing_date = Column(TIMESTAMP)
    discovered_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # Transaction details
    shares = Column(Numeric)
    price = Column(Numeric)
    transaction_value = Column(Numeric)
    
    # Scoring factors (0.0 to 1.0)
    recency_score = Column(Numeric)
    size_score = Column(Numeric)
    competence_score = Column(Numeric)
    consensus_score = Column(Numeric)
    regime_score = Column(Numeric)
    
    # Final conviction
    total_score = Column(Numeric)
    conviction_tier = Column(String(10))
    
    # Tier escalation tracking
    persisted_cycles = Column(Integer, default=0)
    
    # State
    status = Column(String(20), default='ACTIVE', index=True)
    expires_at = Column(TIMESTAMP)
    
    # Cycle management
    cycle_id = Column(String(32), index=True)
    
    # Audit
    raw_data = Column(JSON)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
