"""
Review Cycle Manager for Tier Escalation Confirmation.
Implements hysteresis logic to prevent oscillating between tiers.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from src.models.positions import Position
from src.models.signals import Signal
from src.models.audit_log import AuditLog
from src.execution.order_manager import OrderManager
from src.execution.paper_broker import PaperBroker
from src.utils.logging import get_logger

logger = get_logger(__name__)

class ReviewCycleManager:
    """
    Manages review cycles for tier escalation confirmation.
    
    Rule: A higher-tier signal must persist for two consecutive review cycles
    before triggering an automatic close-and-reopen to prevent oscillation.
    """
    
    # Tier value mapping for comparison
    TIER_VALUES = {
        'S': 4,
        'A': 3, 
        'B': 2,
        'C': 1
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def execute_review_cycle(self) -> Dict:
        """
        Execute a complete review cycle.
        
        Returns:
            Dict with review results and actions taken
        """
        logger.info("Starting review cycle execution")
        
        try:
            # Update signal persistence counters
            self._update_signal_persistence()
            
            # Find potential tier escalations
            escalations = self._find_tier_escalations()
            
            # Execute confirmed escalations
            executed_escalations = self._execute_confirmed_escalations(escalations)
            
            # Log results
            self._log_review_results(executed_escalations)
            
            result = {
                "review_timestamp": datetime.utcnow().isoformat(),
                "potential_escalations": len(escalations),
                "executed_escalations": len(executed_escalations),
                "escalations": executed_escalations
            }
            
            logger.info(
                "Review cycle completed",
                potential_escalations=len(escalations),
                executed_escalations=len(executed_escalations)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Review cycle execution failed: {e}")
            raise
    
    def _update_signal_persistence(self):
        """Update persisted_cycles counter for all active signals."""
        logger.info("Updating signal persistence counters")
        
        # Get all active signals
        active_signals = self.db.query(Signal).filter(
            Signal.status == 'ACTIVE'
        ).all()
        
        updated_count = 0
        for signal in active_signals:
            # Increment persistence counter
            signal.persisted_cycles = (signal.persisted_cycles or 0) + 1
            updated_count += 1
        
        self.db.commit()
        logger.info(f"Updated persistence for {updated_count} signals")
    
    def _find_tier_escalations(self) -> List[Dict]:
        """
        Find potential tier escalations by comparing positions with latest signals.
        
        Returns:
            List of escalation candidates with position and signal info
        """
        logger.info("Finding potential tier escalations")
        
        escalations = []
        
        # Get all open positions
        open_positions = self.db.query(Position).filter(
            Position.status == 'OPEN'
        ).all()
        
        for position in open_positions:
            # Find latest signal for same symbol and direction
            latest_signal = self.db.query(Signal).filter(
                Signal.symbol == position.symbol,
                Signal.direction == position.direction,
                Signal.status == 'ACTIVE'
            ).order_by(Signal.discovered_at.desc()).first()
            
            if not latest_signal:
                continue
            
            # Check for tier escalation
            escalation_info = self._check_tier_escalation(position, latest_signal)
            if escalation_info:
                escalations.append(escalation_info)
        
        logger.info(f"Found {len(escalations)} potential escalations")
        return escalations
    
    def _check_tier_escalation(self, position: Position, signal: Signal) -> Optional[Dict]:
        """
        Check if a position qualifies for tier escalation.
        
        Args:
            position: Current position
            signal: Latest signal for same symbol/direction
            
        Returns:
            Escalation info dict if escalation detected, None otherwise
        """
        position_tier_value = self.TIER_VALUES.get(position.conviction_tier, 0)
        signal_tier_value = self.TIER_VALUES.get(signal.conviction_tier, 0)
        
        # Check if signal is >= 2 tiers higher
        tier_difference = signal_tier_value - position_tier_value
        if tier_difference < 2:
            return None
        
        # Check if signal has persisted for >= 2 cycles
        persisted_cycles = signal.persisted_cycles or 0
        if persisted_cycles < 2:
            return None
        
        return {
            "position_id": position.position_id,
            "symbol": position.symbol,
            "direction": position.direction,
            "current_tier": position.conviction_tier,
            "new_tier": signal.conviction_tier,
            "tier_difference": tier_difference,
            "persisted_cycles": persisted_cycles,
            "signal_id": signal.signal_id,
            "position_shares": position.shares,
            "position_entry_price": position.entry_price
        }
    
    def _execute_confirmed_escalations(self, escalations: List[Dict]) -> List[Dict]:
        """
        Execute confirmed tier escalations by closing current position and opening new one.
        
        Args:
            escalations: List of confirmed escalation candidates
            
        Returns:
            List of executed escalations with results
        """
        logger.info(f"Executing {len(escalations)} confirmed escalations")
        
        executed = []
        
        # Initialize broker and order manager
        broker = PaperBroker()
        broker.connect()
        order_manager = OrderManager(self.db, broker)
        
        try:
            for escalation in escalations:
                try:
                    result = self._execute_single_escalation(escalation, order_manager)
                    executed.append(result)
                    
                except Exception as e:
                    logger.error(f"Failed to execute escalation for {escalation['symbol']}: {e}")
                    executed.append({
                        **escalation,
                        "status": "FAILED",
                        "error": str(e)
                    })
            
        finally:
            broker.disconnect()
        
        logger.info(f"Executed {len(executed)} escalations")
        return executed
    
    def _execute_single_escalation(self, escalation: Dict, order_manager: OrderManager) -> Dict:
        """
        Execute a single tier escalation.
        
        Args:
            escalation: Escalation info
            order_manager: Order manager instance
            
        Returns:
            Execution result with status and details
        """
        position_id = escalation["position_id"]
        symbol = escalation["symbol"]
        new_tier = escalation["new_tier"]
        
        logger.info(
            "Executing tier escalation",
            position_id=position_id,
            symbol=symbol,
            current_tier=escalation["current_tier"],
            new_tier=new_tier
        )
        
        # Get the position
        position = self.db.query(Position).filter(
            Position.position_id == position_id
        ).first()
        
        if not position:
            raise ValueError(f"Position {position_id} not found")
        
        # Close current position
        close_result = order_manager.close_position(
            position_id=position_id,
            reason="TIER_ESCALATION_CONFIRMED"
        )
        
        if not close_result["success"]:
            raise ValueError(f"Failed to close position: {close_result['error']}")
        
        # Create new position with higher tier
        # Get the signal that triggered the escalation
        signal = self.db.query(Signal).filter(
            Signal.signal_id == escalation["signal_id"]
        ).first()
        
        if not signal:
            raise ValueError(f"Signal {escalation['signal_id']} not found")
        
        # Create allocation for new position
        allocation = {
            "symbol": symbol,
            "direction": position.direction,
            "shares": position.shares,  # Keep same size
            "conviction_tier": new_tier,
            "signal_id": signal.signal_id,
            "philosophy_applied": position.philosophy_applied
        }
        
        # Create new position
        new_position_id = f"{symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        
        new_position = Position(
            position_id=new_position_id,
            symbol=symbol,
            direction=position.direction,
            shares=position.shares,
            entry_date=datetime.utcnow(),
            entry_price=position.entry_price,  # Keep same entry price for tracking
            conviction_tier=new_tier,
            philosophy_applied=position.philosophy_applied,
            source_signals=[signal.signal_id],
            round_start=position.round_start,
            round_expiry=position.round_expiry,
            cycle_id=position.cycle_id,
            status='OPEN'
        )
        
        self.db.add(new_position)
        self.db.commit()
        
        # Create audit log entry
        self._create_audit_log(
            event_type='TIER_ESCALATION_EXECUTED',
            entity_type='position',
            entity_id=new_position_id,
            before_state={
                "position_id": position_id,
                "tier": escalation["current_tier"]
            },
            after_state={
                "position_id": new_position_id,
                "tier": new_tier
            },
            reason="TIER_ESCALATION_CONFIRMED"
        )
        
        return {
            **escalation,
            "status": "SUCCESS",
            "old_position_id": position_id,
            "new_position_id": new_position_id,
            "close_result": close_result
        }
    
    def _create_audit_log(self, event_type: str, entity_type: str, entity_id: str, 
                        before_state: Dict, after_state: Dict, reason: str):
        """Create audit log entry for tier escalation."""
        audit_log = AuditLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor='ReviewCycleManager',
            action=f'Tier escalation from {before_state.get("tier", "unknown")} to {after_state.get("tier", "unknown")}',
            reason=reason,
            before_state=before_state,
            after_state=after_state,
            event_hash='',  # TODO: Implement proper hashing
            previous_hash=None
        )
        
        self.db.add(audit_log)
        self.db.commit()
    
    def _log_review_results(self, executed_escalations: List[Dict]):
        """Log summary of review cycle results."""
        successful = len([e for e in executed_escalations if e.get("status") == "SUCCESS"])
        failed = len([e for e in executed_escalations if e.get("status") == "FAILED"])
        
        logger.info(
            "Review cycle results",
            total_escalations=len(executed_escalations),
            successful=successful,
            failed=failed
        )
        
        # Log individual escalations
        for escalation in executed_escalations:
            if escalation.get("status") == "SUCCESS":
                logger.info(
                    "Tier escalation executed",
                    symbol=escalation["symbol"],
                    old_tier=escalation["current_tier"],
                    new_tier=escalation["new_tier"],
                    persisted_cycles=escalation["persisted_cycles"]
                )
            else:
                logger.error(
                    "Tier escalation failed",
                    symbol=escalation["symbol"],
                    error=escalation.get("error")
                )
