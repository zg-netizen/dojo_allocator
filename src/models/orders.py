"""Order database model."""
from sqlalchemy import Column, String, Numeric, TIMESTAMP, Integer, Text
from sqlalchemy.sql import func
from src.models.base import Base

class Order(Base):
    """
    Individual orders sent to broker.
    """
    __tablename__ = 'orders'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    order_id = Column(String(64), unique=True, nullable=False)
    broker_order_id = Column(String(64))
    position_id = Column(String(64))
    
    # Order details
    symbol = Column(String(10), nullable=False)
    side = Column(String(4), nullable=False)
    order_type = Column(String(20), nullable=False)
    quantity = Column(Numeric, nullable=False)
    limit_price = Column(Numeric)
    stop_price = Column(Numeric)
    
    # Execution status
    status = Column(String(20), nullable=False, index=True)
    filled_qty = Column(Numeric, default=0)
    filled_avg_price = Column(Numeric)
    commission = Column(Numeric)
    
    # Timestamps
    submitted_at = Column(TIMESTAMP)
    filled_at = Column(TIMESTAMP)
    
    # Error tracking
    error_message = Column(Text)
    
    # Audit
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
