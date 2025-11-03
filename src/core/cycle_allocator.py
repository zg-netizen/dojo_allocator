"""
Cycle-Based Allocator

This module implements cycle-aware capital allocation that respects 90-day cycle limits
and position sizing constraints.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from src.models.signals import Signal
from src.models.positions import Position
from src.core.cycle_manager import CycleManager, Cycle
from src.core.allocator import Allocator
from src.utils.logging import get_logger

logger = get_logger(__name__)

class CycleAllocator:
    """Cycle-aware capital allocator that respects 90-day cycle constraints."""
    
    def __init__(self, db: Session):
        self.db = db
        self.cycle_manager = CycleManager(db)
        self.base_allocator = Allocator()
        
        # Cycle parameters
        self.MAX_POSITIONS_PER_CYCLE = 50
        self.TARGET_POSITION_SIZE = Decimal('2000.00')
        self.MAX_POSITION_SIZE = Decimal('5000.00')
        self.MIN_POSITION_SIZE = Decimal('500.00')
        
        # Allocation parameters
        self.MAX_PORTFOLIO_RISK = Decimal('0.02')  # 2% max risk per position
        self.POSITION_SIZE_MULTIPLIER = Decimal('1.0')  # Base position size multiplier
        
    def allocate_for_cycle(self, cycle: Cycle, portfolio_value: Decimal) -> List[Dict]:
        """
        Allocate capital for a specific cycle with phase-based logic.
        
        Args:
            cycle: The active cycle
            portfolio_value: Current portfolio value
            
        Returns:
            List of allocation decisions
        """
        logger.info(f"Allocating capital for cycle {cycle.cycle_id}")
        
        # Get current cycle state and phase
        cycle_day = self.cycle_manager.get_current_cycle_day(cycle)
        phase = self.cycle_manager.get_cycle_phase(cycle)
        
        logger.info(f"Cycle {cycle.cycle_id}: Day {cycle_day}, Phase {phase}")
        
        # Check phase-specific allocation rules
        if phase == 'FORCE_CLOSE':
            logger.info(f"Cycle {cycle.cycle_id} in FORCE_CLOSE phase - no new allocations")
            return []
        
        # Get current cycle positions
        current_positions = self.cycle_manager.get_cycle_positions(cycle)
        open_positions = [p for p in current_positions if p.status == 'OPEN']
        
        # Apply phase-specific position limits
        max_positions = self._get_phase_max_positions(phase)
        if len(open_positions) >= max_positions:
            logger.warning(f"Cycle {cycle.cycle_id} at phase limit ({max_positions} positions)")
            return []
        
        # Check drawdown gates
        drawdown_gate = self.cycle_manager.check_drawdown_gates(cycle)
        if drawdown_gate in ['RED', 'NUCLEAR']:
            logger.warning(f"Cycle {cycle.cycle_id} drawdown gate {drawdown_gate} - no new allocations")
            return []
        
        # Get available signals for this cycle
        available_signals = self._get_available_signals(cycle)
        
        if not available_signals:
            logger.info(f"No available signals for cycle {cycle.cycle_id}")
            return []
        
        # Calculate available capital based on phase
        available_capital = self._calculate_phase_capital(cycle, portfolio_value, open_positions, phase)
        
        if available_capital <= 0:
            logger.warning(f"No available capital for cycle {cycle.cycle_id} in phase {phase}")
            return []
        
        # Allocate positions based on phase
        allocation_decisions = self._allocate_positions_by_phase(
            cycle, available_signals, available_capital, open_positions, phase
        )
        
        logger.info(f"Generated {len(allocation_decisions)} allocation decisions for cycle {cycle.cycle_id} (phase {phase})")
        return allocation_decisions
    
    def _get_available_signals(self, cycle: Cycle) -> List[Signal]:
        """Get signals available for allocation in this cycle."""
        # Get active signals not yet allocated to this cycle
        available_signals = self.db.query(Signal).filter(
            Signal.status == 'ACTIVE',
            Signal.cycle_id.is_(None)  # Not yet assigned to a cycle
        ).order_by(Signal.total_score.desc()).limit(100).all()
        
        # Filter out signals for symbols already in cycle
        current_positions = self.cycle_manager.get_cycle_positions(cycle)
        current_symbols = {p.symbol for p in current_positions if p.status == 'OPEN'}
        
        filtered_signals = [s for s in available_signals if s.symbol not in current_symbols]
        
        logger.info(f"Found {len(filtered_signals)} available signals for cycle {cycle.cycle_id}")
        return filtered_signals
    
    def _get_phase_max_positions(self, phase: str) -> int:
        """Get maximum positions allowed for a phase."""
        phase_limits = {
            'LOAD': 12,      # Days 1-7: Load phase (10-12 positions)
            'ACTIVE': 16,    # Days 8-60: Active phase (max 16 positions)
            'SCALE_OUT': 8,  # Days 60-75: Scale out (reduce 50%)
            'FORCE_CLOSE': 0 # Days 76-90: Force close (no new positions)
        }
        return phase_limits.get(phase, 16)
    
    def _calculate_phase_capital(self, cycle: Cycle, portfolio_value: Decimal, open_positions: List[Position], phase: str) -> Decimal:
        """Calculate available capital based on phase."""
        # Calculate total invested in current cycle
        total_invested = sum(
            Decimal(str(float(p.shares) * float(p.entry_price))) for p in open_positions
        )
        
        # Phase-specific capital allocation percentages
        phase_allocation_pct = {
            'LOAD': Decimal('0.70'),     # Days 1-7: Deploy 60-70% capital
            'ACTIVE': Decimal('0.80'),    # Days 8-60: Deploy up to 80% capital
            'SCALE_OUT': Decimal('0.40'), # Days 60-75: Reduce to 40% capital
            'FORCE_CLOSE': Decimal('0.00') # Days 76-90: No new capital
        }
        
        allocation_pct = phase_allocation_pct.get(phase, Decimal('0.80'))
        max_cycle_allocation = float(portfolio_value) * float(allocation_pct)
        
        # Available capital is the minimum of:
        # 1. Remaining cycle allocation
        # 2. Remaining position slots * target position size
        remaining_cycle_allocation = float(max_cycle_allocation) - float(total_invested)
        remaining_slots = self._get_phase_max_positions(phase) - len(open_positions)
        slot_based_capital = remaining_slots * float(cycle.target_position_size)
        
        available_capital = min(remaining_cycle_allocation, slot_based_capital)
        
        logger.info(f"Phase {phase} capital: ${available_capital:,.2f} (max: ${max_cycle_allocation:,.2f})")
        return Decimal(str(available_capital)) if available_capital > 0 else Decimal('0.00')
    
    def _allocate_positions_by_phase(self, cycle: Cycle, signals: List[Signal], available_capital: Decimal, open_positions: List[Position], phase: str) -> List[Dict]:
        """Allocate positions based on phase-specific logic."""
        decisions = []
        
        # Calculate position size based on phase
        remaining_slots = self._get_phase_max_positions(phase) - len(open_positions)
        if remaining_slots <= 0:
            return decisions
        
        # Phase-specific position sizing
        remaining_slots_decimal = Decimal(str(remaining_slots))
        
        if phase == 'LOAD':
            # Load phase: Larger positions, fewer signals
            target_size = available_capital / min(remaining_slots_decimal, Decimal('3'))  # Max 3 positions per allocation
            position_size = max(
                min(float(target_size), float(cycle.max_position_size) * 1.5),  # 1.5x max size
                float(cycle.min_position_size)
            )
        elif phase == 'ACTIVE':
            # Active phase: Standard sizing
            target_size = available_capital / remaining_slots_decimal
            position_size = max(
                min(float(target_size), float(cycle.max_position_size)),
                float(cycle.min_position_size)
            )
        elif phase == 'SCALE_OUT':
            # Scale out phase: Smaller positions, tighter risk
            target_size = available_capital / remaining_slots_decimal
            position_size = max(
                min(float(target_size), float(cycle.max_position_size) * 0.5),  # 0.5x max size
                float(cycle.min_position_size) * 0.5
            )
        else:
            # Default sizing
            target_size = available_capital / remaining_slots_decimal
            position_size = max(
                min(float(target_size), float(cycle.max_position_size)),
                float(cycle.min_position_size)
            )
        
        # Allocate positions for top signals
        max_signals = min(len(signals), remaining_slots)
        for signal in signals[:max_signals]:
            if float(available_capital) < position_size:
                break
            
            decision = {
                'signal_id': signal.signal_id,
                'symbol': signal.symbol,
                'direction': signal.direction,
                'shares': self._calculate_shares(signal, Decimal(str(position_size))),
                'target_price': self._get_target_price(signal),
                'position_size': position_size,
                'conviction_tier': signal.conviction_tier,
                'cycle_id': cycle.cycle_id,
                'phase': phase,
                'allocation_reason': f"Cycle {cycle.cycle_id} {phase} phase allocation"
            }
            
            decisions.append(decision)
            available_capital -= Decimal(str(position_size))
        
        return decisions
    
    def _calculate_available_capital(self, cycle: Cycle, portfolio_value: Decimal, open_positions: List[Position]) -> Decimal:
        """Calculate available capital for new positions."""
        # Calculate total invested in current cycle
        total_invested = sum(
            Decimal(str(float(p.shares) * float(p.entry_price))) for p in open_positions
        )
        
        # Calculate maximum cycle allocation (e.g., 20% of portfolio)
        max_cycle_allocation = float(portfolio_value) * 0.20
        
        # Available capital is the minimum of:
        # 1. Remaining cycle allocation
        # 2. Remaining position slots * target position size
        remaining_cycle_allocation = max_cycle_allocation - float(total_invested)
        remaining_slots = cycle.max_positions - len(open_positions)
        slot_based_capital = remaining_slots * float(cycle.target_position_size)
        
        available_capital = min(remaining_cycle_allocation, slot_based_capital)
        
        logger.info(f"Available capital for cycle {cycle.cycle_id}: ${available_capital:,.2f}")
        return Decimal(str(available_capital)) if available_capital > 0 else Decimal('0.00')
    
    def _allocate_positions(self, cycle: Cycle, signals: List[Signal], available_capital: Decimal, open_positions: List[Position]) -> List[Dict]:
        """Allocate positions based on signals and available capital."""
        decisions = []
        
        # Calculate position size based on available capital and remaining slots
        remaining_slots = cycle.max_positions - len(open_positions)
        if remaining_slots <= 0:
            return decisions
        
        # Target position size for remaining slots
        remaining_slots_decimal = Decimal(str(remaining_slots))
        target_size = available_capital / remaining_slots_decimal
        
        # Ensure position size is within limits
        position_size = max(
            min(float(target_size), float(cycle.max_position_size)),
            float(cycle.min_position_size)
        )
        
        # Allocate positions for top signals
        for signal in signals[:remaining_slots]:
            if float(available_capital) < position_size:
                break
            
            decision = {
                'signal_id': signal.signal_id,
                'symbol': signal.symbol,
                'direction': signal.direction,
                'shares': self._calculate_shares(signal, Decimal(str(position_size))),
                'target_price': self._get_target_price(signal),
                'position_size': position_size,
                'conviction_tier': signal.conviction_tier,
                'cycle_id': cycle.cycle_id,
                'allocation_reason': f"Cycle {cycle.cycle_id} allocation"
            }
            
            decisions.append(decision)
            available_capital -= Decimal(str(position_size))
        
        return decisions
    
    def _calculate_shares(self, signal: Signal, position_size: Decimal) -> int:
        """Calculate number of shares for a position."""
        # Use signal price if available, otherwise use target price
        price = signal.price or self._get_target_price(signal)
        
        if price and price > 0:
            shares = int(position_size / Decimal(str(price)))
            return max(shares, 1)  # Minimum 1 share
        
        # Fallback to dollar-based allocation
        return int(position_size / Decimal('100.00'))  # Assume $100 per share
    
    def _get_target_price(self, signal: Signal) -> Decimal:
        """Get target price for a signal."""
        # Use signal price if available
        if signal.price and signal.price > 0:
            return Decimal(str(signal.price))
        
        # Fallback to default price based on symbol
        default_prices = {
            'AAPL': Decimal('150.00'),
            'MSFT': Decimal('300.00'),
            'GOOGL': Decimal('2800.00'),
            'TSLA': Decimal('800.00'),
            'NVDA': Decimal('450.00'),
        }
        
        return default_prices.get(signal.symbol, Decimal('100.00'))
    
    def rebalance_cycle_positions(self, cycle: Cycle) -> List[Dict]:
        """
        Rebalance existing positions in a cycle.
        
        Returns:
            List of rebalancing decisions
        """
        logger.info(f"Rebalancing positions for cycle {cycle.cycle_id}")
        
        # Get current open positions
        current_positions = self.cycle_manager.get_cycle_positions(cycle)
        open_positions = [p for p in current_positions if p.status == 'OPEN']
        
        if not open_positions:
            logger.info(f"No open positions to rebalance in cycle {cycle.cycle_id}")
            return []
        
        rebalance_decisions = []
        
        # Check each position for rebalancing needs
        for position in open_positions:
            # Calculate current position value
            current_value = Decimal(str(float(position.shares) * float(position.entry_price)))
            
            # Check if position needs rebalancing
            if self._needs_rebalancing(position, cycle):
                decision = {
                    'action': 'rebalance',
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'current_shares': position.shares,
                    'target_shares': self._calculate_target_shares(position, cycle),
                    'reason': 'Position size rebalancing'
                }
                rebalance_decisions.append(decision)
        
        logger.info(f"Generated {len(rebalance_decisions)} rebalancing decisions for cycle {cycle.cycle_id}")
        return rebalance_decisions
    
    def _needs_rebalancing(self, position: Position, cycle: Cycle) -> bool:
        """Check if a position needs rebalancing."""
        current_value = Decimal(str(float(position.shares) * float(position.entry_price)))
        
        # Check if position is outside size limits
        if current_value > cycle.max_position_size:
            return True
        
        if current_value < cycle.min_position_size:
            return True
        
        # Check if position is significantly different from target
        target_value = cycle.target_position_size
        deviation = abs(current_value - target_value) / target_value
        
        if deviation > Decimal('0.20'):  # 20% deviation threshold
            return True
        
        return False
    
    def _calculate_target_shares(self, position: Position, cycle: Cycle) -> int:
        """Calculate target number of shares for rebalancing."""
        target_value = cycle.target_position_size
        current_price = position.entry_price
        
        if current_price and current_price > 0:
            target_shares = int(target_value / Decimal(str(current_price)))
            return max(target_shares, 1)
        
        return position.shares  # No change if price unavailable
    
    def get_cycle_allocation_summary(self, cycle: Cycle) -> Dict:
        """Get summary of cycle allocation status."""
        current_positions = self.cycle_manager.get_cycle_positions(cycle)
        open_positions = [p for p in current_positions if p.status == 'OPEN']
        
        # Calculate allocation metrics
        total_invested = sum(
            Decimal(str(float(p.shares) * float(p.entry_price))) for p in open_positions
        )
        
        remaining_slots = cycle.max_positions - len(open_positions)
        remaining_capacity = remaining_slots * float(cycle.target_position_size)
        
        return {
            'cycle_id': cycle.cycle_id,
            'total_positions': len(current_positions),
            'open_positions': len(open_positions),
            'remaining_slots': remaining_slots,
            'total_invested': float(total_invested),
            'remaining_capacity': float(remaining_capacity),
            'allocation_percent': (len(open_positions) / cycle.max_positions) * 100,
            'investment_percent': (float(total_invested) / float(cycle.target_position_size) / float(cycle.max_positions)) * 100
        }

def example_usage():
    """Example of how to use CycleAllocator."""
    from src.models.base import SessionLocal
    
    db = SessionLocal()
    try:
        allocator = CycleAllocator(db)
        cycle_manager = CycleManager(db)
        
        # Get or create active cycle
        cycle = cycle_manager.get_active_cycle()
        if not cycle:
            cycle = cycle_manager.create_new_cycle()
        
        # Allocate capital for cycle
        portfolio_value = Decimal('100000.00')
        decisions = allocator.allocate_for_cycle(cycle, portfolio_value)
        
        print(f"Generated {len(decisions)} allocation decisions")
        for decision in decisions[:3]:
            print(f"  {decision['symbol']}: {decision['shares']} shares @ ${decision['target_price']}")
        
        # Get allocation summary
        summary = allocator.get_cycle_allocation_summary(cycle)
        print(f"Cycle allocation summary: {summary}")
        
    finally:
        db.close()

if __name__ == '__main__':
    example_usage()
