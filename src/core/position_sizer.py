"""
Position Sizing System

This module implements sophisticated position sizing with:
- ATR-based position sizing
- Spread checks for liquidity
- Liquidity checks for volume
- Min/max position value limits
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session

from src.models.signals import Signal
from src.models.positions import Position
from src.core.cycle_manager import CycleManager, Cycle
from src.utils.logging import get_logger

logger = get_logger(__name__)

class PositionSizer:
    """Advanced position sizing system with ATR, spread, and liquidity checks."""
    
    def __init__(self, db: Session):
        self.db = db
        self.cycle_manager = CycleManager(db)
        
        # Position sizing parameters
        self.MIN_POSITION_VALUE = Decimal('500.00')
        self.MAX_POSITION_VALUE = Decimal('5000.00')
        self.DEFAULT_POSITION_VALUE = Decimal('2000.00')
        
        # Risk parameters
        self.MAX_RISK_PER_POSITION = Decimal('0.02')  # 2% max risk
        self.ATR_RISK_MULTIPLIER = Decimal('2.0')    # 2x ATR for risk calculation
        
        # Spread and liquidity thresholds
        self.MAX_SPREAD_TO_ATR_RATIO = Decimal('0.08')  # 8% max spread/ATR ratio
        self.MIN_DAILY_VOLUME_USD = Decimal('1000000.00')  # $1M min daily volume
        self.MIN_AVG_VOLUME_USD = Decimal('5000000.00')    # $5M min avg volume
        
        # Phase-specific sizing multipliers
        self.PHASE_SIZING_MULTIPLIERS = {
            'LOAD': Decimal('1.5'),      # Days 1-7: 1.5x sizing
            'ACTIVE': Decimal('1.0'),    # Days 8-60: 1.0x sizing
            'SCALE_OUT': Decimal('0.5'), # Days 60-75: 0.5x sizing
            'FORCE_CLOSE': Decimal('0.0') # Days 76-90: 0x sizing
        }
    
    def calculate_position_size(self, signal: Signal, cycle: Cycle, available_capital: Decimal) -> Dict:
        """
        Calculate optimal position size for a signal.
        
        Args:
            signal: Signal to size for
            cycle: Current cycle
            available_capital: Available capital for allocation
            
        Returns:
            Dictionary with sizing decision and metrics
        """
        logger.info(f"Calculating position size for {signal.symbol}")
        
        # Get current phase
        phase = self.cycle_manager.get_cycle_phase(cycle)
        
        # Step 1: Check liquidity and spread requirements
        liquidity_check = self._check_liquidity_requirements(signal)
        if not liquidity_check['passes']:
            return {
                'signal_id': signal.signal_id,
                'symbol': signal.symbol,
                'size': 0,
                'shares': 0,
                'position_value': Decimal('0.00'),
                'reason': f"Liquidity check failed: {liquidity_check['reason']}",
                'passes_checks': False
            }
        
        # Step 2: Calculate ATR-based sizing
        atr_sizing = self._calculate_atr_based_sizing(signal, phase)
        
        # Step 3: Calculate risk-based sizing
        risk_sizing = self._calculate_risk_based_sizing(signal, cycle, available_capital)
        
        # Step 4: Apply phase multiplier
        phase_multiplier = self.PHASE_SIZING_MULTIPLIERS.get(phase, Decimal('1.0'))
        
        # Step 5: Determine final size (minimum of all constraints)
        final_size = min(
            atr_sizing['position_value'],
            risk_sizing['position_value'],
            available_capital
        ) * phase_multiplier
        
        # Step 6: Apply min/max limits
        final_size = max(
            min(final_size, self.MAX_POSITION_VALUE),
            self.MIN_POSITION_VALUE
        )
        
        # Step 7: Calculate shares
        shares = self._calculate_shares(signal, final_size)
        
        # Step 8: Final validation
        if shares <= 0 or final_size < self.MIN_POSITION_VALUE:
            return {
                'signal_id': signal.signal_id,
                'symbol': signal.symbol,
                'size': 0,
                'shares': 0,
                'position_value': Decimal('0.00'),
                'reason': "Position too small after sizing constraints",
                'passes_checks': False
            }
        
        result = {
            'signal_id': signal.signal_id,
            'symbol': signal.symbol,
            'size': final_size,
            'shares': shares,
            'position_value': final_size,
            'phase': phase,
            'phase_multiplier': float(phase_multiplier),
            'atr_sizing': atr_sizing,
            'risk_sizing': risk_sizing,
            'liquidity_check': liquidity_check,
            'passes_checks': True,
            'reason': f"Position sized successfully for {phase} phase"
        }
        
        logger.info(f"Position size for {signal.symbol}: ${final_size:.2f} ({shares} shares)")
        return result
    
    def _check_liquidity_requirements(self, signal: Signal) -> Dict:
        """Check if signal meets liquidity and spread requirements."""
        try:
            # Get market data
            from src.data.market_data import MarketDataProvider
            provider = MarketDataProvider()
            
            # Check daily volume
            daily_volume_usd = provider.get_avg_daily_volume_usd(signal.symbol, days=1)
            if daily_volume_usd < float(self.MIN_DAILY_VOLUME_USD):
                # If volume is 0, skip the check (data unavailable)
                if daily_volume_usd == 0:
                    logger.warning(f"No volume data for {signal.symbol}, skipping volume check")
                else:
                    return {
                        'passes': False,
                        'reason': f"Daily volume ${daily_volume_usd:,.0f} < ${self.MIN_DAILY_VOLUME_USD:,.0f}",
                        'daily_volume_usd': daily_volume_usd,
                        'min_required': float(self.MIN_DAILY_VOLUME_USD)
                    }
            
            # Check average volume
            avg_volume_usd = provider.get_avg_daily_volume_usd(signal.symbol, days=20)
            if avg_volume_usd < float(self.MIN_AVG_VOLUME_USD):
                # If volume is 0, skip the check (data unavailable)
                if avg_volume_usd == 0:
                    logger.warning(f"No avg volume data for {signal.symbol}, skipping avg volume check")
                else:
                    return {
                        'passes': False,
                        'reason': f"Avg volume ${avg_volume_usd:,.0f} < ${self.MIN_AVG_VOLUME_USD:,.0f}",
                        'avg_volume_usd': avg_volume_usd,
                        'min_required': float(self.MIN_AVG_VOLUME_USD)
                    }
            
            # Check spread
            current_price = provider.get_current_price(signal.symbol)
            atr = provider.get_atr(signal.symbol)
            bid_ask_spread = provider.get_bid_ask_spread(signal.symbol)
            
            if current_price and atr and bid_ask_spread:
                spread_to_atr_ratio = bid_ask_spread / atr
                if spread_to_atr_ratio > float(self.MAX_SPREAD_TO_ATR_RATIO):
                    return {
                        'passes': False,
                        'reason': f"Spread/ATR ratio {spread_to_atr_ratio:.3f} > {self.MAX_SPREAD_TO_ATR_RATIO:.3f}",
                        'spread_to_atr_ratio': spread_to_atr_ratio,
                        'max_allowed': float(self.MAX_SPREAD_TO_ATR_RATIO)
                    }
            
            return {
                'passes': True,
                'reason': "All liquidity checks passed",
                'daily_volume_usd': daily_volume_usd,
                'avg_volume_usd': avg_volume_usd,
                'spread_to_atr_ratio': spread_to_atr_ratio if 'spread_to_atr_ratio' in locals() else 0.0
            }
            
        except Exception as e:
            logger.warning(f"Liquidity check failed for {signal.symbol}: {e}")
            # Fallback to basic checks - allow position if we can't get market data
            return {
                'passes': True,
                'reason': "Liquidity check skipped due to data unavailability",
                'warning': str(e),
                'daily_volume_usd': 0.0,
                'avg_volume_usd': 0.0,
                'spread_to_atr_ratio': 0.0
            }
    
    def _calculate_atr_based_sizing(self, signal: Signal, phase: str) -> Dict:
        """Calculate position size based on ATR (volatility)."""
        try:
            # Get ATR for the symbol
            from src.data.market_data import MarketDataProvider
            provider = MarketDataProvider()
            atr = provider.get_atr(signal.symbol)
            
            if not atr or atr <= 0:
                # Fallback to default sizing
                return {
                    'position_value': self.DEFAULT_POSITION_VALUE,
                    'atr': 0.0,
                    'method': 'default_fallback'
                }
            
            # Calculate ATR-based sizing
            # Higher ATR = smaller position size (more volatile = less capital)
            # Lower ATR = larger position size (less volatile = more capital)
            atr_sizing_factor = Decimal('100.00') / Decimal(str(atr))  # Inverse relationship
            atr_sizing_factor = max(Decimal('0.5'), min(atr_sizing_factor, Decimal('2.0')))  # Clamp to 0.5-2.0
            
            position_value = self.DEFAULT_POSITION_VALUE * atr_sizing_factor
            
            return {
                'position_value': position_value,
                'atr': atr,
                'atr_sizing_factor': float(atr_sizing_factor),
                'method': 'atr_based'
            }
            
        except Exception as e:
            logger.warning(f"ATR sizing failed for {signal.symbol}: {e}")
            return {
                'position_value': self.DEFAULT_POSITION_VALUE,
                'atr': 0.0,
                'method': 'error_fallback'
            }
    
    def _calculate_risk_based_sizing(self, signal: Signal, cycle: Cycle, available_capital: Decimal) -> Dict:
        """Calculate position size based on risk limits."""
        try:
            # Get current price
            from src.data.market_data import MarketDataProvider
            provider = MarketDataProvider()
            current_price = provider.get_current_price(signal.symbol)
            
            if not current_price:
                current_price = signal.price or 100.0
            
            # Calculate risk-based sizing
            # Risk = Position Value * (ATR * Risk Multiplier) / Current Price
            # Position Value = Risk Limit / (ATR * Risk Multiplier / Current Price)
            
            atr = provider.get_atr(signal.symbol) or 2.0
            risk_per_share = atr * float(self.ATR_RISK_MULTIPLIER)
            risk_percentage = risk_per_share / current_price
            
            # Calculate maximum position value based on risk limit
            max_risk_value = available_capital * self.MAX_RISK_PER_POSITION
            max_position_value = max_risk_value / Decimal(str(risk_percentage))
            
            # Apply cycle-specific limits
            max_position_value = min(max_position_value, cycle.max_position_size)
            max_position_value = max(max_position_value, cycle.min_position_size)
            
            return {
                'position_value': max_position_value,
                'current_price': current_price,
                'atr': atr,
                'risk_per_share': risk_per_share,
                'risk_percentage': risk_percentage,
                'max_risk_value': float(max_risk_value),
                'method': 'risk_based'
            }
            
        except Exception as e:
            logger.warning(f"Risk sizing failed for {signal.symbol}: {e}")
            return {
                'position_value': self.DEFAULT_POSITION_VALUE,
                'current_price': 100.0,
                'atr': 2.0,
                'method': 'error_fallback'
            }
    
    def _calculate_shares(self, signal: Signal, position_value: Decimal) -> int:
        """Calculate number of shares for a position."""
        try:
            # Get current price
            from src.data.market_data import MarketDataProvider
            provider = MarketDataProvider()
            current_price = provider.get_current_price(signal.symbol)
            
            if not current_price:
                current_price = signal.price or 100.0
            
            # Calculate shares
            shares = int(position_value / Decimal(str(current_price)))
            return max(shares, 1)  # Minimum 1 share
            
        except Exception as e:
            logger.warning(f"Share calculation failed for {signal.symbol}: {e}")
            # Fallback to dollar-based allocation
            return int(position_value / Decimal('100.00'))
    
    def validate_position_size(self, signal: Signal, cycle: Cycle, position_value: Decimal, shares: int) -> Tuple[bool, str]:
        """Validate a position size meets all requirements."""
        try:
            # Check minimum position value
            if position_value < self.MIN_POSITION_VALUE:
                return False, f"Position value ${position_value:.2f} below minimum ${self.MIN_POSITION_VALUE:.2f}"
            
            # Check maximum position value
            if position_value > self.MAX_POSITION_VALUE:
                return False, f"Position value ${position_value:.2f} above maximum ${self.MAX_POSITION_VALUE:.2f}"
            
            # Check minimum shares
            if shares < 1:
                return False, f"Shares {shares} below minimum 1"
            
            # Check liquidity requirements
            liquidity_check = self._check_liquidity_requirements(signal)
            if not liquidity_check['passes']:
                return False, f"Liquidity check failed: {liquidity_check['reason']}"
            
            # Check if position fits in cycle limits
            current_positions = self.cycle_manager.get_cycle_positions(cycle)
            open_positions = [p for p in current_positions if p.status == 'OPEN']
            
            if len(open_positions) >= cycle.max_positions:
                return False, f"Cycle at position limit ({cycle.max_positions})"
            
            return True, "Position size validation passed"
            
        except Exception as e:
            logger.error(f"Position validation failed for {signal.symbol}: {e}")
            return False, f"Validation error: {str(e)}"
    
    def get_sizing_summary(self, cycle: Cycle) -> Dict:
        """Get summary of position sizing parameters for a cycle."""
        phase = self.cycle_manager.get_cycle_phase(cycle)
        phase_multiplier = self.PHASE_SIZING_MULTIPLIERS.get(phase, Decimal('1.0'))
        
        return {
            'cycle_id': cycle.cycle_id,
            'phase': phase,
            'phase_multiplier': float(phase_multiplier),
            'min_position_value': float(self.MIN_POSITION_VALUE),
            'max_position_value': float(self.MAX_POSITION_VALUE),
            'default_position_value': float(self.DEFAULT_POSITION_VALUE),
            'max_risk_per_position': float(self.MAX_RISK_PER_POSITION),
            'atr_risk_multiplier': float(self.ATR_RISK_MULTIPLIER),
            'max_spread_to_atr_ratio': float(self.MAX_SPREAD_TO_ATR_RATIO),
            'min_daily_volume_usd': float(self.MIN_DAILY_VOLUME_USD),
            'min_avg_volume_usd': float(self.MIN_AVG_VOLUME_USD)
        }

def example_usage():
    """Example of how to use PositionSizer."""
    from src.models.base import SessionLocal
    from src.models.signals import Signal
    from decimal import Decimal
    
    db = SessionLocal()
    try:
        sizer = PositionSizer(db)
        cycle_manager = CycleManager(db)
        
        # Get active cycle
        active_cycle = cycle_manager.get_active_cycle()
        if active_cycle:
            print(f"Position sizing for cycle: {active_cycle.cycle_id}")
            
            # Get a sample signal
            signal = db.query(Signal).filter(Signal.status == 'ACTIVE').first()
            if signal:
                print(f"Testing sizing for signal: {signal.symbol}")
                
                # Calculate position size
                available_capital = Decimal('10000.00')
                sizing_result = sizer.calculate_position_size(signal, active_cycle, available_capital)
                
                print(f"Position size: ${sizing_result['position_value']:.2f}")
                print(f"Shares: {sizing_result['shares']}")
                print(f"Phase: {sizing_result['phase']}")
                print(f"Passes checks: {sizing_result['passes_checks']}")
                print(f"Reason: {sizing_result['reason']}")
                
                # Get sizing summary
                summary = sizer.get_sizing_summary(active_cycle)
                print(f"Sizing summary: {summary}")
                
            else:
                print("No active signals found")
        else:
            print("No active cycle found")
            
    finally:
        db.close()

if __name__ == '__main__':
    example_usage()
