"""
End-of-Cycle Settlement System

This module implements comprehensive end-of-cycle settlement including:
- Day-90 force close of all positions
- Cycle validity checks
- Profit withdrawal and capital reset
- Performance calculation and reporting
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.positions import Position
from src.models.cycle_state import CycleState
from src.core.cycle_manager import CycleManager
from src.models.cycles import Cycle
from src.execution.order_manager import OrderManager
from src.execution.paper_broker import PaperBroker
from src.utils.logging import get_logger

logger = get_logger(__name__)

class CycleSettlement:
    """Comprehensive end-of-cycle settlement system."""
    
    def __init__(self, db: Session):
        self.db = db
        self.cycle_manager = CycleManager(db)
        
        # Settlement parameters
        self.CYCLE_DURATION_DAYS = 90
        self.FORCE_CLOSE_DAYS = 76  # Start force close at day 76
        self.MIN_CYCLE_VALIDITY_DAYS = 30  # Minimum 30 days for valid cycle
        self.MIN_POSITIONS_FOR_VALIDITY = 5  # Minimum 5 positions for valid cycle
        
        # Performance thresholds
        self.MIN_PROFIT_THRESHOLD = Decimal('0.02')  # 2% minimum profit threshold
        self.MAX_LOSS_THRESHOLD = Decimal('-0.10')    # 10% maximum loss threshold
        
        # Capital management
        self.PROFIT_WITHDRAWAL_PCT = Decimal('0.50')   # Withdraw 50% of profits
        self.CAPITAL_RESET_PCT = Decimal('0.80')      # Reset to 80% of original capital
    
    def check_cycle_completion(self, cycle: Cycle) -> Dict:
        """
        Check if a cycle should be completed and settled.
        
        Returns:
            Dictionary with completion status and details
        """
        cycle_day = self.cycle_manager.get_current_cycle_day(cycle)
        
        # Check if cycle has reached completion day
        if cycle_day >= self.CYCLE_DURATION_DAYS:
            return {
                'should_complete': True,
                'reason': 'Cycle duration completed (90 days)',
                'cycle_day': cycle_day,
                'completion_type': 'DURATION'
            }
        
        # Check if cycle should start force close
        if cycle_day >= self.FORCE_CLOSE_DAYS:
            return {
                'should_complete': False,
                'should_force_close': True,
                'reason': f'Force close phase started (day {cycle_day})',
                'cycle_day': cycle_day,
                'completion_type': 'FORCE_CLOSE'
            }
        
        # Check for emergency completion conditions
        emergency_check = self._check_emergency_completion(cycle)
        if emergency_check['should_complete']:
            emergency_check['cycle_day'] = cycle_day
            return emergency_check
        
        return {
            'should_complete': False,
            'should_force_close': False,
            'reason': f'Cycle ongoing (day {cycle_day})',
            'cycle_day': cycle_day,
            'completion_type': 'ONGOING'
        }
    
    def _check_emergency_completion(self, cycle: Cycle) -> Dict:
        """Check for emergency completion conditions."""
        # Check drawdown gates
        from src.core.risk_manager import RiskManager
        risk_manager = RiskManager(self.db)
        drawdown_gate, drawdown_metrics = risk_manager.check_dual_drawdown_gates(cycle)
        
        if drawdown_gate == 'NUCLEAR':
            return {
                'should_complete': True,
                'reason': 'Nuclear drawdown gate triggered',
                'drawdown_gate': drawdown_gate,
                'completion_type': 'EMERGENCY'
            }
        
        # Check if all positions are closed
        positions = self.cycle_manager.get_cycle_positions(cycle)
        open_positions = [p for p in positions if p.status == 'OPEN']
        
        if len(open_positions) == 0:
            return {
                'should_complete': True,
                'reason': 'All positions closed',
                'open_positions': 0,
                'completion_type': 'ALL_CLOSED'
            }
        
        return {
            'should_complete': False,
            'reason': 'No emergency conditions met'
        }
    
    def validate_cycle(self, cycle: Cycle) -> Dict:
        """
        Validate cycle for settlement eligibility.
        
        Returns:
            Dictionary with validation results
        """
        cycle_day = self.cycle_manager.get_current_cycle_day(cycle)
        positions = self.cycle_manager.get_cycle_positions(cycle)
        
        # Check minimum duration
        if cycle_day < self.MIN_CYCLE_VALIDITY_DAYS:
            return {
                'is_valid': False,
                'reason': f'Cycle too short: {cycle_day} days < {self.MIN_CYCLE_VALIDITY_DAYS} days',
                'cycle_day': cycle_day,
                'min_required': self.MIN_CYCLE_VALIDITY_DAYS
            }
        
        # Check minimum positions
        if len(positions) < self.MIN_POSITIONS_FOR_VALIDITY:
            return {
                'is_valid': False,
                'reason': f'Too few positions: {len(positions)} < {self.MIN_POSITIONS_FOR_VALIDITY}',
                'position_count': len(positions),
                'min_required': self.MIN_POSITIONS_FOR_VALIDITY
            }
        
        # Check cycle status
        if cycle.status != 'ACTIVE':
            return {
                'is_valid': False,
                'reason': f'Cycle not active: {cycle.status}',
                'cycle_status': cycle.status
            }
        
        return {
            'is_valid': True,
            'reason': 'Cycle validation passed',
            'cycle_day': cycle_day,
            'position_count': len(positions),
            'cycle_status': cycle.status
        }
    
    def force_close_all_positions(self, cycle: Cycle) -> Dict:
        """
        Force close all open positions in a cycle.
        
        Returns:
            Dictionary with force close results
        """
        logger.info(f"Force closing all positions for cycle {cycle.cycle_id}")
        
        positions = self.cycle_manager.get_cycle_positions(cycle)
        open_positions = [p for p in positions if p.status == 'OPEN']
        
        if not open_positions:
            return {
                'status': 'success',
                'message': 'No open positions to close',
                'positions_closed': 0,
                'total_pnl': 0.0
            }
        
        # Use emergency liquidation to close all positions
        from src.execution.paper_broker import PaperBroker
        broker = PaperBroker()
        broker.connect()
        
        order_manager = OrderManager(self.db, broker)
        liquidation_results = order_manager.emergency_liquidate(
            positions=open_positions,
            levels=['ALL'],  # Close all positions
            conviction_tiers=['ALL']  # All conviction tiers
        )
        
        # Calculate total P&L
        total_pnl = 0.0
        if 'closed' in liquidation_results:
            for closed_position in liquidation_results['closed']:
                if 'partial_pnl' in closed_position:
                    total_pnl += float(closed_position['partial_pnl'])
                elif 'realized_pnl' in closed_position:
                    total_pnl += float(closed_position['realized_pnl'])
        
        return {
            'status': 'success',
            'message': f'Force closed {len(open_positions)} positions',
            'positions_closed': len(open_positions),
            'total_pnl': total_pnl,
            'liquidation_results': liquidation_results
        }
    
    def calculate_cycle_performance(self, cycle: Cycle) -> Dict:
        """
        Calculate comprehensive cycle performance metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        positions = self.cycle_manager.get_cycle_positions(cycle)
        
        if not positions:
            return {
                'total_positions': 0,
                'total_invested': 0.0,
                'total_return': 0.0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'avg_winner': 0.0,
                'avg_loser': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'cycle_validity': 'INVALID'
            }
        
        # Calculate basic metrics
        total_positions = len(positions)
        closed_positions = [p for p in positions if p.status == 'CLOSED']
        
        # Calculate financial metrics
        total_invested = sum(float(p.shares * p.entry_price) for p in positions)
        total_pnl = sum(float(p.realized_pnl or 0) for p in closed_positions)
        total_return = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        # Calculate win/loss metrics
        winners = [p for p in closed_positions if p.realized_pnl and p.realized_pnl > 0]
        losers = [p for p in closed_positions if p.realized_pnl and p.realized_pnl < 0]
        
        win_rate = (len(winners) / len(closed_positions) * 100) if closed_positions else 0
        avg_winner = sum(float(p.realized_pnl) for p in winners) / len(winners) if winners else 0
        avg_loser = sum(float(p.realized_pnl) for p in losers) / len(losers) if losers else 0
        
        # Calculate drawdown (simplified)
        max_drawdown = 0.0  # Would need historical data for accurate calculation
        
        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = 0.0  # Would need risk-free rate and volatility data
        
        # Determine cycle validity
        cycle_validity = 'VALID'
        if total_return < float(self.MIN_PROFIT_THRESHOLD) * 100:
            cycle_validity = 'LOW_PROFIT'
        if total_return < float(self.MAX_LOSS_THRESHOLD) * 100:
            cycle_validity = 'HIGH_LOSS'
        
        return {
            'total_positions': total_positions,
            'closed_positions': len(closed_positions),
            'total_invested': total_invested,
            'total_return': total_return,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'cycle_validity': cycle_validity,
            'winners': len(winners),
            'losers': len(losers)
        }
    
    def withdraw_profits(self, cycle: Cycle, performance: Dict) -> Dict:
        """
        Withdraw profits from cycle performance.
        
        Returns:
            Dictionary with withdrawal details
        """
        total_pnl = performance['total_pnl']
        
        if total_pnl <= 0:
            return {
                'status': 'skipped',
                'message': 'No profits to withdraw',
                'total_pnl': total_pnl,
                'withdrawal_amount': 0.0
            }
        
        # Calculate withdrawal amount
        withdrawal_amount = Decimal(str(total_pnl)) * self.PROFIT_WITHDRAWAL_PCT
        
        # In a real system, this would transfer funds to external account
        # For now, we'll just log the withdrawal
        logger.info(f"Withdrawing ${withdrawal_amount:.2f} from cycle {cycle.cycle_id} (50% of ${total_pnl:.2f} profit)")
        
        return {
            'status': 'success',
            'message': f'Withdrew ${withdrawal_amount:.2f} (50% of profits)',
            'total_pnl': total_pnl,
            'withdrawal_amount': float(withdrawal_amount),
            'withdrawal_pct': float(self.PROFIT_WITHDRAWAL_PCT)
        }
    
    def reset_capital(self, cycle: Cycle, performance: Dict) -> Dict:
        """
        Reset capital for next cycle.
        
        Returns:
            Dictionary with capital reset details
        """
        # Get current portfolio value
        broker = PaperBroker()
        broker.connect()
        current_portfolio_value = broker.get_account_value()
        
        # Calculate reset amount (80% of original capital)
        # In a real system, this would be based on starting capital
        original_capital = Decimal('100000.00')  # Mock original capital
        reset_amount = original_capital * self.CAPITAL_RESET_PCT
        
        # Calculate remaining capital after reset
        remaining_capital = current_portfolio_value - reset_amount
        
        logger.info(f"Resetting capital for cycle {cycle.cycle_id}: ${reset_amount:.2f} (80% of original)")
        
        return {
            'status': 'success',
            'message': f'Capital reset to ${reset_amount:.2f}',
            'original_capital': float(original_capital),
            'reset_amount': float(reset_amount),
            'remaining_capital': float(remaining_capital),
            'reset_pct': float(self.CAPITAL_RESET_PCT)
        }
    
    def settle_cycle(self, cycle: Cycle) -> Dict:
        """
        Complete cycle settlement process.
        
        Returns:
            Dictionary with settlement results
        """
        logger.info(f"Starting settlement for cycle {cycle.cycle_id}")
        
        # Step 1: Validate cycle
        validation = self.validate_cycle(cycle)
        if not validation['is_valid']:
            return {
                'status': 'failed',
                'message': f'Cycle validation failed: {validation["reason"]}',
                'validation': validation
            }
        
        # Step 2: Force close all positions
        force_close_result = self.force_close_all_positions(cycle)
        if force_close_result['status'] != 'success':
            return {
                'status': 'failed',
                'message': f'Force close failed: {force_close_result["message"]}',
                'force_close_result': force_close_result
            }
        
        # Step 3: Calculate performance
        performance = self.calculate_cycle_performance(cycle)
        
        # Step 4: Withdraw profits
        withdrawal_result = self.withdraw_profits(cycle, performance)
        
        # Step 5: Reset capital
        capital_reset_result = self.reset_capital(cycle, performance)
        
        # Step 6: Mark cycle as completed
        cycle.status = 'COMPLETED'
        cycle.updated_at = datetime.utcnow()
        self.db.commit()
        
        # Step 7: Create new cycle
        new_cycle = self.cycle_manager.create_new_cycle()
        
        settlement_result = {
            'status': 'success',
            'message': f'Cycle {cycle.cycle_id} settled successfully',
            'cycle_id': cycle.cycle_id,
            'validation': validation,
            'force_close_result': force_close_result,
            'performance': performance,
            'withdrawal_result': withdrawal_result,
            'capital_reset_result': capital_reset_result,
            'new_cycle_id': new_cycle.cycle_id,
            'settlement_timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Cycle {cycle.cycle_id} settlement completed: {performance['total_return']:.2f}% return")
        return settlement_result
    
    def get_settlement_summary(self, cycle: Cycle) -> Dict:
        """Get summary of cycle settlement status."""
        completion_check = self.check_cycle_completion(cycle)
        validation = self.validate_cycle(cycle)
        performance = self.calculate_cycle_performance(cycle)
        
        return {
            'cycle_id': cycle.cycle_id,
            'cycle_day': completion_check['cycle_day'],
            'should_complete': completion_check['should_complete'],
            'should_force_close': completion_check.get('should_force_close', False),
            'completion_reason': completion_check['reason'],
            'is_valid': validation['is_valid'],
            'validation_reason': validation['reason'],
            'performance': performance,
            'settlement_ready': completion_check['should_complete'] and validation['is_valid']
        }

def example_usage():
    """Example of how to use CycleSettlement."""
    from src.models.base import SessionLocal
    
    db = SessionLocal()
    try:
        settlement = CycleSettlement(db)
        cycle_manager = CycleManager(db)
        
        # Get active cycle
        active_cycle = cycle_manager.get_active_cycle()
        if active_cycle:
            print(f"Settlement analysis for cycle: {active_cycle.cycle_id}")
            
            # Check completion status
            completion_check = settlement.check_cycle_completion(active_cycle)
            print(f"Should complete: {completion_check['should_complete']}")
            print(f"Should force close: {completion_check.get('should_force_close', False)}")
            print(f"Reason: {completion_check['reason']}")
            
            # Validate cycle
            validation = settlement.validate_cycle(active_cycle)
            print(f"Cycle valid: {validation['is_valid']}")
            print(f"Validation reason: {validation['reason']}")
            
            # Get performance
            performance = settlement.calculate_cycle_performance(active_cycle)
            print(f"Total return: {performance['total_return']:.2f}%")
            print(f"Win rate: {performance['win_rate']:.2f}%")
            print(f"Cycle validity: {performance['cycle_validity']}")
            
            # Get settlement summary
            summary = settlement.get_settlement_summary(active_cycle)
            print(f"Settlement ready: {summary['settlement_ready']}")
            
        else:
            print("No active cycle found")
            
    finally:
        db.close()

if __name__ == '__main__':
    example_usage()
