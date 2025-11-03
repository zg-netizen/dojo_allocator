"""
Advanced Risk Management System

This module implements sophisticated risk management features including:
- Dual drawdown gates (current vs max drawdown)
- ATR-based stop losses
- Cash reserve management
- Position-level risk controls
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.positions import Position
from src.models.cycle_state import CycleState
from src.core.cycle_manager import CycleManager, Cycle
from src.utils.logging import get_logger

logger = get_logger(__name__)

class RiskManager:
    """Advanced risk management system for 90-day cycles."""
    
    def __init__(self, db: Session):
        self.db = db
        self.cycle_manager = CycleManager(db)
        
        # Drawdown gate thresholds
        self.DRAWDOWN_GATES = {
            'GREEN': {'current': 0.00, 'max': 0.00},      # No restrictions
            'YELLOW': {'current': 0.05, 'max': 0.10},     # 5% current, 10% max
            'RED': {'current': 0.10, 'max': 0.15},         # 10% current, 15% max
            'NUCLEAR': {'current': 0.15, 'max': 0.20}     # 15% current, 20% max
        }
        
        # ATR-based stop loss multipliers
        self.ATR_STOP_MULTIPLIERS = {
            'LOAD': 2.0,      # Days 1-7: 2x ATR stops
            'ACTIVE': 1.5,    # Days 8-60: 1.5x ATR stops
            'SCALE_OUT': 1.0, # Days 60-75: 1x ATR stops
            'FORCE_CLOSE': 0.5 # Days 76-90: 0.5x ATR stops
        }
        
        # Cash reserve requirements
        self.CASH_RESERVE_TARGETS = {
            'LOAD': 0.30,     # Days 1-7: 30% cash reserve
            'ACTIVE': 0.20,   # Days 8-60: 20% cash reserve
            'SCALE_OUT': 0.60, # Days 60-75: 60% cash reserve
            'FORCE_CLOSE': 1.00 # Days 76-90: 100% cash reserve
        }
        
        # Position risk limits
        self.MAX_POSITION_RISK = Decimal('0.02')  # 2% max risk per position
        self.MAX_CORRELATION_RISK = Decimal('0.05')  # 5% max correlated risk
    
    def check_dual_drawdown_gates(self, cycle: Cycle) -> Tuple[str, Dict]:
        """
        Check dual drawdown gates (current vs max drawdown).
        
        Returns:
            Tuple of (gate_status, detailed_metrics)
        """
        # Get cycle state
        cycle_state = self.db.query(CycleState).filter(
            CycleState.cycle_id == cycle.cycle_id
        ).order_by(CycleState.cycle_day.desc()).first()
        
        if not cycle_state:
            return 'GREEN', {'current_drawdown': 0.0, 'max_drawdown': 0.0, 'high_water_mark': 0.0}
        
        # Calculate current metrics
        current_dd = float(cycle_state.current_drawdown)
        max_dd = float(cycle_state.max_drawdown)
        high_water_mark = float(cycle_state.high_water_mark)
        
        # Determine gate status based on thresholds
        gate_status = 'GREEN'
        for gate, thresholds in self.DRAWDOWN_GATES.items():
            if current_dd >= thresholds['current'] or max_dd >= thresholds['max']:
                gate_status = gate
        
        metrics = {
            'current_drawdown': current_dd,
            'max_drawdown': max_dd,
            'high_water_mark': high_water_mark,
            'gate_status': gate_status,
            'thresholds': self.DRAWDOWN_GATES[gate_status]
        }
        
        logger.info(f"Drawdown gates for cycle {cycle.cycle_id}: {gate_status} (current: {current_dd:.2%}, max: {max_dd:.2%})")
        return gate_status, metrics
    
    def calculate_atr_stop_loss(self, position: Position, phase: str) -> Optional[Decimal]:
        """
        Calculate ATR-based stop loss for a position.
        
        Args:
            position: Position to calculate stop for
            phase: Current cycle phase
            
        Returns:
            Stop loss price or None if calculation fails
        """
        try:
            # Get ATR for the symbol
            atr = self._get_atr_for_symbol(position.symbol)
            if not atr or atr <= 0:
                logger.warning(f"No ATR available for {position.symbol}")
                return None
            
            # Get phase-specific multiplier
            multiplier = self.ATR_STOP_MULTIPLIERS.get(phase, 1.5)
            
            # Calculate stop loss
            if position.direction == 'LONG':
                # Long position: stop below entry price
                stop_loss = position.entry_price - (Decimal(str(atr)) * Decimal(str(multiplier)))
            else:
                # Short position: stop above entry price
                stop_loss = position.entry_price + (Decimal(str(atr)) * Decimal(str(multiplier)))
            
            logger.info(f"ATR stop for {position.symbol}: ${stop_loss:.2f} (ATR: ${atr:.2f}, multiplier: {multiplier}x)")
            return Decimal(str(stop_loss))
            
        except Exception as e:
            logger.error(f"Error calculating ATR stop for {position.symbol}: {e}")
            return None
    
    def _get_atr_for_symbol(self, symbol: str) -> Optional[float]:
        """Get Average True Range for a symbol."""
        try:
            # Try to get ATR from market data provider
            from src.data.market_data import MarketDataProvider
            provider = MarketDataProvider()
            atr = provider.get_atr(symbol)
            
            if atr and atr > 0:
                return atr
                
        except Exception as e:
            logger.warning(f"Failed to get ATR for {symbol}: {e}")
        
        # Fallback to mock ATR data
        mock_atr = {
            'AAPL': 3.5,
            'MSFT': 4.2,
            'GOOGL': 25.0,
            'TSLA': 15.0,
            'NVDA': 8.5,
            'META': 5.0,
            'NFLX': 6.0,
            'AMZN': 12.0
        }
        
        return mock_atr.get(symbol.upper(), 2.0)
    
    def check_cash_reserve_requirements(self, cycle: Cycle, portfolio_value: Decimal) -> Tuple[bool, Dict]:
        """
        Check if cash reserve requirements are met.
        
        Returns:
            Tuple of (meets_requirements, reserve_metrics)
        """
        # Get current phase
        phase = self.cycle_manager.get_cycle_phase(cycle)
        target_reserve_pct = self.CASH_RESERVE_TARGETS.get(phase, 0.20)
        
        # Get cycle state
        cycle_state = self.db.query(CycleState).filter(
            CycleState.cycle_id == cycle.cycle_id
        ).order_by(CycleState.cycle_day.desc()).first()
        
        if not cycle_state:
            return True, {'target_reserve_pct': target_reserve_pct, 'actual_reserve_pct': 0.0}
        
        # Calculate actual cash reserve
        total_invested = float(cycle_state.current_equity)
        actual_reserve_pct = (float(portfolio_value) - total_invested) / float(portfolio_value)
        
        meets_requirements = actual_reserve_pct >= target_reserve_pct
        
        metrics = {
            'phase': phase,
            'target_reserve_pct': target_reserve_pct,
            'actual_reserve_pct': actual_reserve_pct,
            'total_invested': total_invested,
            'portfolio_value': float(portfolio_value),
            'meets_requirements': meets_requirements
        }
        
        logger.info(f"Cash reserve check for cycle {cycle.cycle_id}: {meets_requirements} (target: {target_reserve_pct:.1%}, actual: {actual_reserve_pct:.1%})")
        return meets_requirements, metrics
    
    def calculate_position_risk(self, position: Position, current_price: Optional[Decimal] = None) -> Dict:
        """
        Calculate risk metrics for a position.
        
        Returns:
            Dictionary with risk metrics
        """
        if not current_price:
            current_price = position.entry_price
        
        # Calculate position value
        position_value = position.shares * current_price
        
        # Calculate unrealized P&L
        if position.direction == 'LONG':
            unrealized_pnl = (current_price - position.entry_price) * position.shares
        else:
            unrealized_pnl = (position.entry_price - current_price) * position.shares
        
        # Calculate risk percentage
        risk_pct = abs(float(unrealized_pnl)) / float(position_value) if position_value > 0 else 0
        
        # Calculate ATR-based stop loss
        phase = self.cycle_manager.get_cycle_phase(
            self.cycle_manager.get_active_cycle()
        ) if self.cycle_manager.get_active_cycle() else 'ACTIVE'
        
        atr_stop = self.calculate_atr_stop_loss(position, phase)
        
        metrics = {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'direction': position.direction,
            'shares': position.shares,
            'entry_price': float(position.entry_price),
            'current_price': float(current_price),
            'position_value': float(position_value),
            'unrealized_pnl': float(unrealized_pnl),
            'risk_pct': risk_pct,
            'atr_stop_loss': float(atr_stop) if atr_stop else None,
            'phase': phase
        }
        
        return metrics
    
    def check_position_risk_limits(self, position: Position, current_price: Optional[Decimal] = None) -> Tuple[bool, str]:
        """
        Check if a position violates risk limits.
        
        Returns:
            Tuple of (within_limits, violation_reason)
        """
        risk_metrics = self.calculate_position_risk(position, current_price)
        
        # Check position risk limit
        if risk_metrics['risk_pct'] > float(self.MAX_POSITION_RISK):
            return False, f"Position risk {risk_metrics['risk_pct']:.2%} exceeds limit {self.MAX_POSITION_RISK:.2%}"
        
        # Check if stop loss is triggered
        atr_stop = risk_metrics['atr_stop_loss']
        if atr_stop and current_price:
            if position.direction == 'LONG' and current_price <= atr_stop:
                return False, f"ATR stop loss triggered: ${current_price:.2f} <= ${atr_stop:.2f}"
            elif position.direction == 'SHORT' and current_price >= atr_stop:
                return False, f"ATR stop loss triggered: ${current_price:.2f} >= ${atr_stop:.2f}"
        
        return True, "Within risk limits"
    
    def get_cycle_risk_summary(self, cycle: Cycle) -> Dict:
        """Get comprehensive risk summary for a cycle."""
        # Get cycle state
        cycle_state = self.db.query(CycleState).filter(
            CycleState.cycle_id == cycle.cycle_id
        ).order_by(CycleState.cycle_day.desc()).first()
        
        if not cycle_state:
            return {'error': 'No cycle state found'}
        
        # Get positions
        positions = self.cycle_manager.get_cycle_positions(cycle)
        open_positions = [p for p in positions if p.status == 'OPEN']
        
        # Calculate risk metrics
        total_risk = 0.0
        positions_at_risk = 0
        atr_stops_triggered = 0
        
        for position in open_positions:
            risk_metrics = self.calculate_position_risk(position)
            total_risk += risk_metrics['risk_pct']
            
            if risk_metrics['risk_pct'] > float(self.MAX_POSITION_RISK):
                positions_at_risk += 1
            
            if risk_metrics['atr_stop_loss']:
                if position.direction == 'LONG' and position.entry_price <= risk_metrics['atr_stop_loss']:
                    atr_stops_triggered += 1
                elif position.direction == 'SHORT' and position.entry_price >= risk_metrics['atr_stop_loss']:
                    atr_stops_triggered += 1
        
        # Check drawdown gates
        drawdown_gate, drawdown_metrics = self.check_dual_drawdown_gates(cycle)
        
        # Check cash reserves
        portfolio_value = Decimal('100000.00')  # Mock portfolio value
        meets_cash_reserve, cash_metrics = self.check_cash_reserve_requirements(cycle, portfolio_value)
        
        summary = {
            'cycle_id': cycle.cycle_id,
            'phase': self.cycle_manager.get_cycle_phase(cycle),
            'cycle_day': self.cycle_manager.get_current_cycle_day(cycle),
            'total_positions': len(positions),
            'open_positions': len(open_positions),
            'total_risk_pct': total_risk,
            'positions_at_risk': positions_at_risk,
            'atr_stops_triggered': atr_stops_triggered,
            'drawdown_gate': drawdown_gate,
            'drawdown_metrics': drawdown_metrics,
            'cash_reserve_ok': meets_cash_reserve,
            'cash_metrics': cash_metrics,
            'risk_status': 'HIGH' if drawdown_gate in ['RED', 'NUCLEAR'] or positions_at_risk > 0 else 'NORMAL'
        }
        
        return summary
    
    def update_cycle_risk_metrics(self, cycle: Cycle) -> CycleState:
        """Update cycle risk metrics in the database."""
        # Get or create cycle state
        cycle_day = self.cycle_manager.get_current_cycle_day(cycle)
        cycle_state = self.db.query(CycleState).filter(
            CycleState.cycle_id == cycle.cycle_id,
            CycleState.cycle_day == cycle_day
        ).first()
        
        if not cycle_state:
            cycle_state = CycleState(
                cycle_id=cycle.cycle_id,
                cycle_day=cycle_day,
                phase=self.cycle_manager.get_cycle_phase(cycle)
            )
            self.db.add(cycle_state)
        
        # Update risk metrics
        drawdown_gate, drawdown_metrics = self.check_dual_drawdown_gates(cycle)
        cycle_state.drawdown_gate_status = drawdown_gate
        cycle_state.current_drawdown = Decimal(str(drawdown_metrics['current_drawdown']))
        cycle_state.max_drawdown = Decimal(str(drawdown_metrics['max_drawdown']))
        cycle_state.high_water_mark = Decimal(str(drawdown_metrics['high_water_mark']))
        
        # Update cash reserve metrics
        portfolio_value = Decimal('100000.00')  # Mock portfolio value
        meets_cash_reserve, cash_metrics = self.check_cash_reserve_requirements(cycle, portfolio_value)
        cycle_state.cash_reserve_target = Decimal(str(cash_metrics['target_reserve_pct']))
        cycle_state.cash_reserve_actual = Decimal(str(cash_metrics['actual_reserve_pct']))
        
        self.db.commit()
        return cycle_state

def example_usage():
    """Example of how to use RiskManager."""
    from src.models.base import SessionLocal
    
    db = SessionLocal()
    try:
        risk_manager = RiskManager(db)
        cycle_manager = CycleManager(db)
        
        # Get active cycle
        active_cycle = cycle_manager.get_active_cycle()
        if active_cycle:
            print(f"Risk analysis for cycle: {active_cycle.cycle_id}")
            
            # Check drawdown gates
            gate_status, drawdown_metrics = risk_manager.check_dual_drawdown_gates(active_cycle)
            print(f"Drawdown gate: {gate_status}")
            print(f"Current drawdown: {drawdown_metrics['current_drawdown']:.2%}")
            print(f"Max drawdown: {drawdown_metrics['max_drawdown']:.2%}")
            
            # Check cash reserves
            portfolio_value = Decimal('100000.00')
            meets_reserve, cash_metrics = risk_manager.check_cash_reserve_requirements(active_cycle, portfolio_value)
            print(f"Cash reserve OK: {meets_reserve}")
            print(f"Target reserve: {cash_metrics['target_reserve_pct']:.1%}")
            print(f"Actual reserve: {cash_metrics['actual_reserve_pct']:.1%}")
            
            # Get risk summary
            risk_summary = risk_manager.get_cycle_risk_summary(active_cycle)
            print(f"Risk status: {risk_summary['risk_status']}")
            print(f"Positions at risk: {risk_summary['positions_at_risk']}")
            
        else:
            print("No active cycle found")
            
    finally:
        db.close()

if __name__ == '__main__':
    example_usage()
