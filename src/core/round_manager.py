"""
Trade round lifecycle management.
Implements Japanese discipline: fixed rounds with start, expiry, and review.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from src.models.positions import Position
from src.models.signals import Signal
from src.utils.logging import get_logger
from config.settings import get_philosophy_config

logger = get_logger(__name__)

class RoundManager:
    """
    Manages trade rounds with strict boundaries.
    
    A "round" is a bounded trading cycle with:
    - Fixed start time
    - Fixed expiry time
    - Fixed risk allocation
    - Mandatory post-round review
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.philosophy = get_philosophy_config()
    
    def create_round(self, signal: Signal, allocation: Dict) -> Dict:
        """
        Initialize a new trading round.
        
        Args:
            signal: Signal triggering this position
            allocation: Allocation decision with risk info
        
        Returns:
            Round parameters (start, expiry, risk)
        """
        round_duration_days = self.philosophy['japanese_discipline']['rules']['fixed_round_duration_days']
        round_start = datetime.utcnow()
        round_expiry = round_start + timedelta(days=round_duration_days)
        
        round_params = {
            'round_start': round_start,
            'round_expiry': round_expiry,
            'round_extended': False,
            'max_risk': Decimal(allocation.get('risk_per_trade', 0)),
            'signal_id': signal.signal_id
        }
        
        logger.info(
            "Round created",
            signal_id=signal.signal_id,
            start=round_start.isoformat(),
            expiry=round_expiry.isoformat(),
            duration_days=round_duration_days,
            max_risk=float(round_params['max_risk'])
        )
        
        return round_params
    
    def check_expiry(self, position: Position) -> bool:
        """
        Check if a position's round has expired.
        
        Args:
            position: Position to check
        
        Returns:
            True if round is still active, False if expired
        """
        now = datetime.utcnow()
        
        if now > position.round_expiry:
            logger.info(
                "Round expired",
                position_id=position.position_id,
                symbol=position.symbol,
                expiry=position.round_expiry.isoformat(),
                current_time=now.isoformat()
            )
            return False
        
        time_remaining = position.round_expiry - now
        logger.debug(
            "Round still active",
            position_id=position.position_id,
            days_remaining=time_remaining.days
        )
        return True
    
    def extend_round(self, position: Position, reason: str = "saylor_conviction") -> bool:
        """
        Extend a round (Saylor conviction scaling).
        
        Args:
            position: Position to extend
            reason: Reason for extension
        
        Returns:
            True if extended, False if not allowed
        """
        extension_days = self.philosophy['saylor']['rules']['extension_period_days']
        max_extensions = self.philosophy['saylor']['rules']['max_extension_periods']
        
        current_extensions = self._count_extensions(position)
        
        if current_extensions >= max_extensions:
            logger.warning(
                "Max extensions reached",
                position_id=position.position_id,
                current_extensions=current_extensions,
                max_allowed=max_extensions
            )
            return False
        
        new_expiry = position.round_expiry + timedelta(days=extension_days)
        
        position.round_expiry = new_expiry
        position.round_extended = True
        self.db.commit()
        
        logger.info(
            "Round extended",
            position_id=position.position_id,
            new_expiry=new_expiry.isoformat(),
            extension_days=extension_days,
            reason=reason
        )
        
        return True
    
    def force_close_expired(self) -> List[Position]:
        """
        Force close all positions with expired rounds.
        
        Returns:
            List of positions that were force closed
        """
        now = datetime.utcnow()
        
        expired_positions = self.db.query(Position).filter(
            Position.status == 'OPEN',
            Position.round_expiry < now
        ).all()
        
        if not expired_positions:
            logger.info("No expired positions to close")
            return []
        
        logger.info(
            "Force closing expired positions",
            count=len(expired_positions)
        )
        
        for position in expired_positions:
            logger.info(
                "Force closing expired round",
                position_id=position.position_id,
                symbol=position.symbol,
                expiry=position.round_expiry.isoformat(),
                days_overdue=(now - position.round_expiry).days
            )
            position.status = 'FORCE_CLOSED'
        
        self.db.commit()
        return expired_positions
    
    def conduct_post_round_review(self, position: Position) -> Dict:
        """
        Mandatory review after round completion.
        
        Args:
            position: Completed position to review
        
        Returns:
            Review summary dict
        """
        logger.info(
            "Conducting post-round review",
            position_id=position.position_id,
            symbol=position.symbol
        )
        
        if position.exit_date:
            duration_days = (position.exit_date - position.entry_date).days
        else:
            duration_days = None
        
        review = {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'direction': position.direction,
            'entry_date': position.entry_date.isoformat(),
            'exit_date': position.exit_date.isoformat() if position.exit_date else None,
            'duration_days': duration_days,
            'return_pct': float(position.return_pct) if position.return_pct else None,
            'realized_pnl': float(position.realized_pnl) if position.realized_pnl else None,
            'conviction_tier': position.conviction_tier,
            'philosophy_applied': position.philosophy_applied,
            'discipline_violations': position.discipline_violations,
            'round_extended': position.round_extended,
            'entry_value': float(position.entry_value),
            'exit_value': float(position.exit_value) if position.exit_value else None
        }
        
        if position.return_pct:
            if position.return_pct >= Decimal(0.15):
                review['outcome'] = 'EXCELLENT'
                review['grade'] = 'A+'
            elif position.return_pct >= Decimal(0.08):
                review['outcome'] = 'GOOD'
                review['grade'] = 'A'
            elif position.return_pct >= Decimal(0.05):
                review['outcome'] = 'SATISFACTORY'
                review['grade'] = 'B'
            elif position.return_pct >= Decimal(0.00):
                review['outcome'] = 'BREAK_EVEN'
                review['grade'] = 'C'
            else:
                review['outcome'] = 'LOSS'
                review['grade'] = 'F'
        else:
            review['outcome'] = 'INCOMPLETE'
            review['grade'] = 'N/A'
        
        review['lessons'] = self._extract_lessons(position, review)
        
        logger.info("Post-round review complete", **review)
        return review
    
    def _extract_lessons(self, position: Position, review: Dict) -> List[str]:
        """Extract lessons learned from the round."""
        lessons = []
        
        if review['outcome'] == 'EXCELLENT' and position.conviction_tier in ['S', 'A']:
            lessons.append(f"High conviction tier {position.conviction_tier} performed well - trust the scoring system")
        elif review['outcome'] == 'LOSS' and position.conviction_tier in ['S', 'A']:
            lessons.append(f"High conviction tier {position.conviction_tier} still lost - even best signals fail sometimes")
        elif review['outcome'] in ['GOOD', 'EXCELLENT'] and position.conviction_tier in ['B', 'C']:
            lessons.append(f"Low conviction tier {position.conviction_tier} outperformed - luck or scoring improvement needed?")
        
        if position.philosophy_applied == 'pabrai_cluster' and review['outcome'] in ['GOOD', 'EXCELLENT']:
            lessons.append("Pabrai cluster strategy worked - continue following smart money clusters")
        elif position.philosophy_applied == 'pabrai_cluster' and review['outcome'] == 'LOSS':
            lessons.append("Pabrai cluster failed - even consensus can be wrong")
        
        if position.round_extended and review['outcome'] in ['GOOD', 'EXCELLENT']:
            lessons.append("Saylor extension was correct - high Sharpe positions deserve more time")
        elif position.round_extended and review['outcome'] == 'LOSS':
            lessons.append("Saylor extension didn't work - reconsider extension criteria")
        
        if position.discipline_violations > 0:
            lessons.append(f"Had {position.discipline_violations} discipline violations - focus on following rules")
        else:
            lessons.append("Perfect discipline maintained - no violations")
        
        if duration_days := review.get('duration_days'):
            if duration_days < 30 and review['outcome'] in ['GOOD', 'EXCELLENT']:
                lessons.append("Quick winner - good entry timing")
            elif duration_days > 50 and review['outcome'] in ['BREAK_EVEN', 'LOSS']:
                lessons.append("Held too long - should have exited earlier")
        
        return lessons
    
    def _count_extensions(self, position: Position) -> int:
        """Count how many times a position has been extended."""
        return 1 if position.round_extended else 0
