"""Audit log database model."""
from sqlalchemy import Column, String, TIMESTAMP, Integer, JSON
from sqlalchemy.sql import func
from src.models.base import Base

class AuditLog(Base):
    """
    Immutable audit trail with blockchain-like integrity.
    """
    __tablename__ = 'audit_log'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    
    # Event details
    event_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    
    # Actor and action
    actor = Column(String(50), nullable=False)
    action = Column(String(255), nullable=False)
    reason = Column(String(255))
    
    # State snapshots
    before_state = Column(JSON)
    after_state = Column(JSON)
    
    # Cryptographic integrity
    event_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64))
