"""Cryptographic hashing for audit trail integrity."""
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

def decimal_default(obj):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def create_event_hash(
    timestamp: datetime,
    event_type: str,
    entity_id: str,
    after_state: Dict[str, Any]
) -> str:
    """
    Create SHA-256 hash of event for audit trail.
    """
    event_data = {
        'timestamp': timestamp.isoformat(),
        'event_type': event_type,
        'entity_id': entity_id,
        'after_state': after_state
    }
    
    # Create canonical JSON with Decimal handling
    canonical_json = json.dumps(event_data, sort_keys=True, default=decimal_default)
    
    # Hash
    hash_obj = hashlib.sha256(canonical_json.encode('utf-8'))
    return hash_obj.hexdigest()

def verify_audit_chain(audit_logs: list) -> bool:
    """Verify integrity of audit log chain."""
    if len(audit_logs) < 2:
        return True
    
    for i in range(1, len(audit_logs)):
        current = audit_logs[i]
        previous = audit_logs[i - 1]
        
        if current.previous_hash != previous.event_hash:
            return False
    
    return True
