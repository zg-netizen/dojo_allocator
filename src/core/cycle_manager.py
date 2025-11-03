"""
90-Day Cycle Management System

This module implements the core 90-day cycle system for position management,
including cycle creation, position limits, rebalancing, and performance tracking.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, Numeric, TIMESTAMP
from sqlalchemy.sql import func
from src.models.base import Base
from src.models.signals import Signal
from src.models.positions import Position
from src.models.cycle_state import CycleState
from src.models.cycles import Cycle
from src.utils.logging import get_logger

logger = get_logger(__name__)

class CycleManager:
    """Manages 90-day trading cycles."""
    
    def __init__(self, db: Session):
        self.db = db
        self.CYCLE_DURATION_DAYS = 30
        self.MAX_POSITIONS_PER_CYCLE = 50
        self.TARGET_POSITION_SIZE = Decimal('2000.00')
        self.MAX_POSITION_SIZE = Decimal('5000.00')
        self.MIN_POSITION_SIZE = Decimal('500.00')
        
    def create_new_cycle(self, start_date: Optional[datetime] = None) -> Cycle:
        """
        Create a new 90-day trading cycle.
        
        Args:
            start_date: Start date for the cycle (defaults to now)
            
        Returns:
            New Cycle object
        """
        if start_date is None:
            start_date = datetime.utcnow()
        
        end_date = start_date + timedelta(days=self.CYCLE_DURATION_DAYS)
        
        # Generate unique cycle ID
        cycle_id = f"cycle_{start_date.strftime('%Y%m%d_%H%M%S')}"
        
        # Check if cycle already exists
        existing = self.db.query(Cycle).filter(Cycle.cycle_id == cycle_id).first()
        if existing:
            logger.warning(f"Cycle {cycle_id} already exists")
            return existing
        
        # Create new cycle
        cycle = Cycle(
            cycle_id=cycle_id,
            start_date=start_date,
            end_date=end_date,
            status='ACTIVE',
            max_positions=self.MAX_POSITIONS_PER_CYCLE,
            target_position_size=self.TARGET_POSITION_SIZE,
            max_position_size=self.MAX_POSITION_SIZE,
            min_position_size=self.MIN_POSITION_SIZE
        )
        
        self.db.add(cycle)
        self.db.commit()
        
        logger.info(f"Created new cycle: {cycle_id} ({start_date.date()} to {end_date.date()})")
        return cycle
    
    def get_active_cycle(self) -> Optional[Cycle]:
        """Get the currently active cycle."""
        # Get the most recent active cycle (by creation time)
        active_cycle = self.db.query(Cycle).filter(
            Cycle.status == 'ACTIVE',
            Cycle.end_date > datetime.utcnow()
        ).order_by(Cycle.created_at.desc()).first()
        
        # If multiple active cycles exist, deactivate older ones
        if active_cycle:
            older_active_cycles = self.db.query(Cycle).filter(
                Cycle.status == 'ACTIVE',
                Cycle.end_date > datetime.utcnow(),
                Cycle.id != active_cycle.id
            ).all()
            
            for older_cycle in older_active_cycles:
                logger.warning(f"Deactivating older active cycle: {older_cycle.cycle_id}")
                older_cycle.status = 'CANCELLED'
            
            if older_active_cycles:
                self.db.commit()
        
        return active_cycle
    
    def get_cycle_positions(self, cycle: Cycle) -> List[Position]:
        """Get all positions for a specific cycle."""
        return self.db.query(Position).filter(
            Position.cycle_id == cycle.cycle_id
        ).all()
    
    def get_cycle_signals(self, cycle: Cycle) -> List[Signal]:
        """Get all signals analyzed during a cycle."""
        return self.db.query(Signal).filter(
            Signal.cycle_id == cycle.cycle_id
        ).all()
    
    def calculate_cycle_performance(self, cycle: Cycle) -> Dict:
        """
        Calculate performance metrics for a cycle.
        
        Returns:
            Dictionary with performance metrics
        """
        positions = self.get_cycle_positions(cycle)
        
        if not positions:
            return {
                'total_positions': 0,
                'open_positions': 0,
                'closed_positions': 0,
                'total_invested': 0.0,
                'total_return': 0.0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'avg_winner': 0.0,
                'avg_loser': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0
            }
        
        # Calculate basic metrics
        total_positions = len(positions)
        open_positions = len([p for p in positions if p.status == 'OPEN'])
        closed_positions = len([p for p in positions if p.status == 'CLOSED'])
        
        # Calculate financial metrics
        total_invested = sum(float(p.shares * p.entry_price) for p in positions)
        total_pnl = sum(float(p.realized_pnl or 0) for p in positions if p.status == 'CLOSED')
        total_return = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        # Calculate win/loss metrics
        winners = [p for p in positions if p.status == 'CLOSED' and p.realized_pnl and p.realized_pnl > 0]
        losers = [p for p in positions if p.status == 'CLOSED' and p.realized_pnl and p.realized_pnl < 0]
        
        win_rate = (len(winners) / closed_positions * 100) if closed_positions > 0 else 0
        avg_winner = sum(float(p.realized_pnl) for p in winners) / len(winners) if winners else 0
        avg_loser = sum(float(p.realized_pnl) for p in losers) / len(losers) if losers else 0
        
        # Calculate risk metrics
        returns = [float(p.realized_pnl or 0) for p in positions if p.status == 'CLOSED']
        max_drawdown = self._calculate_max_drawdown(returns)
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        
        return {
            'total_positions': total_positions,
            'open_positions': open_positions,
            'closed_positions': closed_positions,
            'total_invested': total_invested,
            'total_return': total_return,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio
        }
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from returns."""
        if not returns:
            return 0.0
        
        peak = returns[0]
        max_dd = 0.0
        
        for ret in returns:
            if ret > peak:
                peak = ret
            dd = (peak - ret) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd * 100
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio from returns."""
        if len(returns) < 2:
            return 0.0
        
        import numpy as np
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Assume risk-free rate of 2% annually
        risk_free_rate = 0.02 / 365  # Daily risk-free rate
        sharpe = (mean_return - risk_free_rate) / std_return
        
        return sharpe
    
    def update_cycle_performance(self, cycle: Cycle):
        """Update cycle performance metrics in database."""
        performance = self.calculate_cycle_performance(cycle)
        
        cycle.total_invested = Decimal(str(performance['total_invested']))
        cycle.total_return = Decimal(str(performance['total_return']))
        cycle.total_pnl = Decimal(str(performance['total_pnl']))
        cycle.win_rate = Decimal(str(performance['win_rate']))
        cycle.avg_winner = Decimal(str(performance['avg_winner']))
        cycle.avg_loser = Decimal(str(performance['avg_loser']))
        cycle.positions_opened = performance['total_positions']
        cycle.positions_closed = performance['closed_positions']
        
        self.db.commit()
        
        logger.info(f"Updated cycle {cycle.cycle_id} performance: {performance['total_return']:.2f}% return")
    
    def check_cycle_completion(self, cycle: Cycle) -> bool:
        """
        Check if a cycle should be completed.
        
        Returns:
            True if cycle should be completed
        """
        now = datetime.utcnow()
        
        # Check if cycle has ended
        if now >= cycle.end_date:
            return True
        
        # Check if all positions are closed
        positions = self.get_cycle_positions(cycle)
        open_positions = [p for p in positions if p.status == 'OPEN']
        
        if len(open_positions) == 0:
            return True
        
        # Check if cycle has been running for 90 days
        days_running = (now - cycle.start_date).days
        if days_running >= self.CYCLE_DURATION_DAYS:
            return True
        
        return False
    
    def complete_cycle(self, cycle: Cycle) -> Dict:
        """
        Complete a cycle and prepare for the next one.
        
        Returns:
            Dictionary with completion summary
        """
        # Update final performance
        self.update_cycle_performance(cycle)
        
        # Close any remaining open positions
        positions = self.get_cycle_positions(cycle)
        open_positions = [p for p in positions if p.status == 'OPEN']
        
        closed_count = 0
        for position in open_positions:
            # Mark position as closed (emergency liquidation)
            position.status = 'CLOSED'
            position.exit_price = position.entry_price  # Assume no change for now
            position.realized_pnl = Decimal('0.00')
            closed_count += 1
        
        # Mark cycle as completed
        cycle.status = 'COMPLETED'
        cycle.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # Calculate final performance
        final_performance = self.calculate_cycle_performance(cycle)
        
        logger.info(f"Completed cycle {cycle.cycle_id}: {final_performance['total_return']:.2f}% return")
        
        return {
            'cycle_id': cycle.cycle_id,
            'status': 'COMPLETED',
            'positions_closed': closed_count,
            'final_performance': final_performance
        }
    
    def get_cycle_summary(self, cycle: Cycle) -> Dict:
        """Get a summary of cycle status and performance."""
        performance = self.calculate_cycle_performance(cycle)
        
        now = datetime.utcnow()
        days_remaining = (cycle.end_date - now).days if now < cycle.end_date else 0
        days_elapsed = (now - cycle.start_date).days
        
        return {
            'cycle_id': cycle.cycle_id,
            'status': cycle.status,
            'start_date': cycle.start_date.isoformat(),
            'end_date': cycle.end_date.isoformat(),
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'progress_percent': (days_elapsed / self.CYCLE_DURATION_DAYS) * 100,
            'performance': performance
        }
    
    def get_current_cycle_day(self, cycle: Cycle) -> int:
        """Get the current day of the cycle (1-30)."""
        now = datetime.utcnow()
        days_elapsed = (now - cycle.start_date).days + 1
        return min(30, max(1, days_elapsed))
    
    def get_cycle_phase(self, cycle: Cycle) -> str:
        """Determine the current phase of the cycle."""
        cycle_day = self.get_current_cycle_day(cycle)
        
        if cycle_day <= 7:
            return 'LOAD'
        elif cycle_day <= 60:
            return 'ACTIVE'
        elif cycle_day <= 75:
            return 'SCALE_OUT'
        else:
            return 'FORCE_CLOSE'
    
    def should_scale_out(self, cycle: Cycle) -> bool:
        """Check if cycle should enter scale-out phase (days 60-75)."""
        cycle_day = self.get_current_cycle_day(cycle)
        return 60 <= cycle_day <= 75
    
    def should_force_close(self, cycle: Cycle) -> bool:
        """Check if cycle should force close all positions (days 76+)."""
        cycle_day = self.get_current_cycle_day(cycle)
        return cycle_day >= 76
    
    def check_drawdown_gates(self, cycle: Cycle) -> str:
        """Check drawdown gates and return status (GREEN/YELLOW/RED/NUCLEAR)."""
        # Get cycle state
        cycle_state = self.db.query(CycleState).filter(
            CycleState.cycle_id == cycle.cycle_id
        ).order_by(CycleState.cycle_day.desc()).first()
        
        if not cycle_state:
            return 'GREEN'
        
        current_dd = float(cycle_state.current_drawdown)
        max_dd = float(cycle_state.max_drawdown)
        
        # Drawdown gate thresholds
        if current_dd >= 0.15 or max_dd >= 0.20:  # 15% current or 20% max
            return 'NUCLEAR'
        elif current_dd >= 0.10 or max_dd >= 0.15:  # 10% current or 15% max
            return 'RED'
        elif current_dd >= 0.05 or max_dd >= 0.10:  # 5% current or 10% max
            return 'YELLOW'
        else:
            return 'GREEN'
    
    def update_cycle_state(self, cycle: Cycle) -> CycleState:
        """Update or create cycle state tracking."""
        cycle_day = self.get_current_cycle_day(cycle)
        phase = self.get_cycle_phase(cycle)
        drawdown_gate = self.check_drawdown_gates(cycle)
        
        # Get or create cycle state
        cycle_state = self.db.query(CycleState).filter(
            CycleState.cycle_id == cycle.cycle_id,
            CycleState.cycle_day == cycle_day
        ).first()
        
        if not cycle_state:
            cycle_state = CycleState(
                cycle_id=cycle.cycle_id,
                cycle_day=cycle_day,
                phase=phase,
                drawdown_gate_status=drawdown_gate
            )
            self.db.add(cycle_state)
        
        # Update state
        cycle_state.phase = phase
        cycle_state.drawdown_gate_status = drawdown_gate
        
        # Calculate performance metrics
        performance = self.calculate_cycle_performance(cycle)
        cycle_state.total_invested = Decimal(str(performance['total_invested']))
        cycle_state.total_return = Decimal(str(performance['total_return']))
        cycle_state.total_pnl = Decimal(str(performance['total_pnl']))
        cycle_state.win_rate = Decimal(str(performance['win_rate']))
        cycle_state.avg_winner = Decimal(str(performance['avg_winner']))
        cycle_state.avg_loser = Decimal(str(performance['avg_loser']))
        cycle_state.max_drawdown = Decimal(str(performance['max_drawdown']))
        
        # Update position counts
        positions = self.get_cycle_positions(cycle)
        cycle_state.positions_opened = len(positions)
        cycle_state.positions_closed = len([p for p in positions if p.status == 'CLOSED'])
        
        self.db.commit()
        return cycle_state

def example_usage():
    """Example of how to use CycleManager."""
    from src.models.base import SessionLocal
    
    db = SessionLocal()
    try:
        manager = CycleManager(db)
        
        # Create a new cycle
        cycle = manager.create_new_cycle()
        print(f"Created cycle: {cycle.cycle_id}")
        
        # Get cycle summary
        summary = manager.get_cycle_summary(cycle)
        print(f"Cycle summary: {summary}")
        
        # Check if cycle should be completed
        should_complete = manager.check_cycle_completion(cycle)
        print(f"Should complete: {should_complete}")
        
    finally:
        db.close()

if __name__ == '__main__':
    example_usage()
