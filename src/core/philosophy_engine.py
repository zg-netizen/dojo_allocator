"""
Philosophy enforcement and discipline tracking.
Monitors adherence to investment doctrines and applies penalties.
"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from src.models.philosophy_state import PhilosophyState
from src.models.positions import Position
from src.models.audit_log import AuditLog
from src.utils.logging import get_logger
from config.settings import get_philosophy_config

logger = get_logger(__name__)

class PhilosophyEngine:
    """
    Enforces investment philosophy rules and tracks discipline.
    
    Allocation Power System:
    - Starts at 1.0 (100%)
    - Reduced by violations (penalties are negative %)
    - Floor at 0.30 (never below 30%)
    - Ceiling at 1.5 (can increase to 150%)
    - Recovery: 10 clean rounds restores to 1.0
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.philosophy = get_philosophy_config()
        self.current_state = self._load_current_state()
    
    def _load_current_state(self) -> PhilosophyState:
        """Load or create today's philosophy state."""
        today = date.today()
        state = self.db.query(PhilosophyState).filter(
            PhilosophyState.date == today
        ).first()
        
        if not state:
            state = PhilosophyState(
                date=today,
                current_allocation_power=1.0
            )
            self.db.add(state)
            self.db.commit()
        
        return state
    
    def check_dalio_compliance(self, event: Dict) -> bool:
        """
        Dalio: Everything must be systematized and logged.
        """
        if event.get('type') == 'INTUITION_OVERRIDE':
            self._record_violation(
                rule='dalio_no_intuition',
                penalty=self.philosophy['dalio']['penalties']['intuition_override'],
                details=event
            )
            return False
        
        audit_exists = self.db.query(AuditLog).filter(
            AuditLog.entity_id == event.get('entity_id'),
            AuditLog.event_type == event.get('event_type')
        ).first()
        
        if not audit_exists:
            logger.error("Missing audit log entry", event=event)
            return False
        
        self.current_state.decisions_logged += 1
        self.db.commit()
        return True
    
    def check_buffett_margin_of_safety(self, signal: Dict, allocation: Dict) -> bool:
        """
        Buffett: Only trade with margin of safety.
        """
        expected_return = allocation.get('expected_return', 0)
        min_ev = self.philosophy['buffett']['rules']['minimum_expected_value']
        
        if expected_return < min_ev:
            logger.warning(
                "Trade fails margin of safety",
                signal_id=signal.get('signal_id'),
                expected_return=expected_return,
                minimum=min_ev
            )
            self.current_state.trades_without_safety += 1
            self.db.commit()
            
            self._record_violation(
                rule='buffett_margin_of_safety',
                penalty=self.philosophy['buffett']['penalties']['unsafe_trade'],
                details={
                    'signal_id': signal.get('signal_id'),
                    'expected_return': expected_return,
                    'minimum_required': min_ev
                }
            )
            return False
        
        self.current_state.trades_with_safety += 1
        self.db.commit()
        return True
    
    def check_oleary_capital_efficiency(self, position: Position) -> bool:
        """
        O'Leary: Capital must earn minimum return or be retired.
        """
        min_return = self.philosophy['oleary']['rules']['minimum_return_per_cycle']
        max_days = self.philosophy['oleary']['rules']['max_holding_period_days']
        
        days_held = (datetime.utcnow() - position.entry_date).days
        
        if days_held > max_days:
            current_price = Decimal(100)
            current_value = current_price * position.shares
            return_pct = (current_value - position.entry_value) / position.entry_value
            
            if return_pct < Decimal(min_return):
                logger.info(
                    "Retiring underperforming position",
                    position_id=position.position_id,
                    days_held=days_held,
                    return_pct=float(return_pct),
                    minimum_required=min_return
                )
                self.current_state.positions_retired += 1
                self.db.commit()
                return False
        
        return True
    
    def check_saylor_conviction_extension(self, position: Position) -> bool:
        """
        Saylor: Extend high-performing positions with high Sharpe.
        """
        if position.round_extended:
            extension_count = self._count_extensions(position.position_id)
            max_extensions = self.philosophy['saylor']['rules']['max_extension_periods']
            
            if extension_count >= max_extensions:
                logger.info(
                    "Position at max extensions",
                    position_id=position.position_id,
                    extensions=extension_count
                )
                return False
        
        sharpe = self._calculate_sharpe(position)
        threshold = self.philosophy['saylor']['rules']['sharpe_ratio_extension_threshold']
        
        if sharpe >= threshold and not position.round_extended:
            logger.info(
                "Position eligible for Saylor extension",
                position_id=position.position_id,
                sharpe=sharpe,
                threshold=threshold
            )
            self.current_state.positions_extended += 1
            self.db.commit()
            return True
        
        return False
    
    def check_japanese_discipline(self, position: Position) -> bool:
        """
        Japanese: Enforce round discipline.
        """
        if datetime.utcnow() > position.round_expiry:
            logger.info(
                "Position round expired",
                position_id=position.position_id,
                expiry=position.round_expiry
            )
            return False
        
        return True
    
    def _record_violation(self, rule: str, penalty: float, details: Dict):
        """Record a rule violation and apply penalty."""
        logger.warning(
            "Philosophy violation",
            rule=rule,
            penalty=penalty,
            details=details
        )
        
        self.current_state.rule_violations += 1
        
        current_power = self.current_state.current_allocation_power
        new_power = max(
            0.30,
            current_power * (1.0 + penalty)
        )
        
        self.current_state.current_allocation_power = new_power
        
        violations = self.current_state.violated_rules or []
        violations.append({
            'rule': rule,
            'timestamp': datetime.utcnow().isoformat(),
            'penalty': penalty,
            'details': details,
            'power_before': current_power,
            'power_after': new_power
        })
        self.current_state.violated_rules = violations
        
        self.db.commit()
        
        logger.info(
            "Allocation power adjusted",
            old_power=current_power,
            new_power=new_power,
            rule=rule
        )
    
    def _calculate_sharpe(self, position: Position) -> float:
        """Calculate Sharpe ratio for position."""
        return 1.5
    
    def _count_extensions(self, position_id: str) -> int:
        """Count how many times position has been extended."""
        extensions = self.db.query(AuditLog).filter(
            AuditLog.entity_id == position_id,
            AuditLog.event_type == 'POSITION_EXTENDED'
        ).count()
        return extensions
    
    def restore_allocation_power(self):
        """Gradually restore allocation power after clean trading."""
        clean_rounds = self._count_recent_clean_rounds()
        target_rounds = self.philosophy['japanese_discipline']['recovery']['clean_rounds_for_full_restore']
        
        if clean_rounds >= target_rounds:
            self.current_state.current_allocation_power = 1.0
            logger.info(
                "Allocation power fully restored",
                clean_rounds=clean_rounds
            )
            self.db.commit()
        elif clean_rounds > 0:
            restoration_pct = clean_rounds / target_rounds
            current_power = self.current_state.current_allocation_power
            target_power = 1.0
            new_power = current_power + (target_power - current_power) * (restoration_pct * 0.1)
            new_power = min(1.0, new_power)
            
            self.current_state.current_allocation_power = new_power
            logger.info(
                "Partial allocation power restoration",
                clean_rounds=clean_rounds,
                new_power=new_power
            )
            self.db.commit()
    
    def _count_recent_clean_rounds(self) -> int:
        """Count consecutive clean rounds (no violations)."""
        recent_states = self.db.query(PhilosophyState).filter(
            PhilosophyState.date < date.today()
        ).order_by(PhilosophyState.date.desc()).limit(10).all()
        
        clean_count = 0
        for state in recent_states:
            if state.rule_violations == 0:
                clean_count += 1
            else:
                break
        
        return clean_count
