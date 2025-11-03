"""
Position sizing and capital allocation engine.
Maps conviction tiers to position sizes with philosophy overlays.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from decimal import Decimal
from src.models.signals import Signal
from src.models.positions import Position
from src.utils.logging import get_logger
from config.settings import get_risk_limits, get_philosophy_config

logger = get_logger(__name__)

@dataclass
class AllocationDecision:
    """Output of allocation engine."""
    signal_id: str
    symbol: str
    direction: str
    shares: int
    target_value: Decimal
    conviction_tier: str
    philosophy_applied: str
    risk_per_trade: Decimal
    reason: str

class Allocator:
    """
    Converts conviction scores into position sizes.
    
    Allocation Flow:
    1. Start with base size from conviction tier
    2. Apply allocation power (discipline multiplier)
    3. Apply philosophy rules (e.g., Pabrai 2x for clusters)
    4. Calculate dollar amount and share count
    5. Verify available capital
    """
    
    def __init__(self):
        self.risk_limits = get_risk_limits()
        self.philosophy = get_philosophy_config()
        self.sizing_tiers = self.risk_limits['position_sizing']['sizing_tiers']
    
    def allocate_capital(
        self,
        signals: List[Signal],
        current_portfolio_value: Decimal,
        open_positions: List[Position],
        allocation_power: float = 1.0
    ) -> List[AllocationDecision]:
        """
        Determine position sizes for all active signals.
        
        Args:
            signals: Ranked signals ready for execution
            current_portfolio_value: Total account value
            open_positions: Currently open positions
            allocation_power: Current discipline multiplier (0.3 to 1.5)
        
        Returns:
            List of allocation decisions
        """
        decisions = []
        
        max_deployable = current_portfolio_value * Decimal(
            self.risk_limits['portfolio']['max_cash_deployed']
        )
        deployed_capital = sum(
            pos.entry_value for pos in open_positions if pos.status == 'OPEN'
        )
        available_capital = max_deployable - deployed_capital
        
        logger.info(
            "Starting allocation",
            portfolio_value=float(current_portfolio_value),
            deployed=float(deployed_capital),
            available=float(available_capital),
            allocation_power=allocation_power
        )
        
        for signal in signals:
            if signal.conviction_tier == 'REJECT':
                continue
            
            base_size_pct = Decimal(self.sizing_tiers[signal.conviction_tier])
            adjusted_size_pct = base_size_pct * Decimal(allocation_power)
            
            philosophy_multiplier, philosophy_name = self._apply_philosophy_rules(
                signal, signals
            )
            final_size_pct = adjusted_size_pct * Decimal(philosophy_multiplier)
            
            target_value = current_portfolio_value * final_size_pct
            
            if target_value > available_capital:
                logger.warning(
                    "Insufficient capital",
                    signal_id=signal.signal_id,
                    needed=float(target_value),
                    available=float(available_capital)
                )
                continue
            
            current_price = Decimal(100)  # TODO: Fetch real price
            shares = int(target_value / current_price)
            
            if shares == 0:
                logger.warning(
                    "Position too small",
                    signal_id=signal.signal_id,
                    target_value=float(target_value)
                )
                continue
            
            decision = AllocationDecision(
                signal_id=signal.signal_id,
                symbol=signal.symbol,
                direction=signal.direction,
                shares=shares,
                target_value=target_value,
                conviction_tier=signal.conviction_tier,
                philosophy_applied=philosophy_name,
                risk_per_trade=self._calculate_risk(target_value, signal),
                reason=f"Tier {signal.conviction_tier}, {philosophy_name}"
            )
            
            decisions.append(decision)
            available_capital -= target_value
            
            logger.info(
                "Allocation decision",
                signal_id=signal.signal_id,
                symbol=signal.symbol,
                shares=shares,
                value=float(target_value),
                philosophy=philosophy_name
            )
        
        return decisions
    
    def _apply_philosophy_rules(
        self,
        signal: Signal,
        all_signals: List[Signal]
    ) -> tuple:
        """Apply investment philosophy multipliers."""
        cluster_signals = [
            s for s in all_signals
            if s.symbol == signal.symbol
            and s.direction == signal.direction
            and s.status == 'ACTIVE'
        ]
        
        cluster_threshold = self.philosophy['pabrai']['rules']['cluster_signal_threshold']
        
        if len(cluster_signals) >= cluster_threshold:
            multiplier = self.philosophy['pabrai']['rules']['position_sizing_multiplier']
            logger.info(
                "Pabrai cluster detected",
                symbol=signal.symbol,
                cluster_size=len(cluster_signals),
                multiplier=multiplier
            )
            return (multiplier, "pabrai_cluster")
        
        return (1.0, "standard")
    
    def _calculate_risk(self, position_value: Decimal, signal: Signal) -> Decimal:
        """Calculate risk per trade based on stop loss."""
        stop_loss_pct = Decimal(
            self.risk_limits['stop_loss']['tier_adjustments'][signal.conviction_tier]
        )
        risk = position_value * stop_loss_pct
        
        max_risk_per_round = Decimal(
            self.philosophy['japanese_discipline']['rules']['fixed_risk_per_round']
        )
        
        if stop_loss_pct > max_risk_per_round:
            logger.warning(
                "Risk exceeds round limit",
                calculated_risk_pct=float(stop_loss_pct),
                max_allowed_pct=float(max_risk_per_round)
            )
            risk = position_value * max_risk_per_round
        
        return risk
