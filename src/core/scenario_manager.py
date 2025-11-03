"""
Scenario Manager for parallel execution of different trading strategies.
Each scenario runs independently with its own philosophy settings and paper trading environment.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from src.models.scenarios import Scenario, ScenarioPosition, ScenarioTrade
from src.models.signals import Signal
from src.core.cycle_manager import CycleManager
from src.core.cycle_allocator import CycleAllocator
from src.core.philosophy_engine import PhilosophyEngine
from src.execution.paper_broker import PaperBroker
from src.execution.order_manager import OrderManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScenarioManager:
    """
    Manages parallel execution of multiple trading scenarios.
    Each scenario has its own philosophy settings, positions, and performance tracking.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.scenarios = {}
        self.brokers = {}
        self.order_managers = {}
        self.cycle_managers = {}
        self.cycle_allocators = {}
        self.philosophy_engines = {}
    
    def initialize_scenarios(self):
        """Initialize all 5 scenarios with their default settings."""
        # First, initialize components for existing scenarios
        scenario_names = ["Conservative", "Balanced", "Aggressive", "High-Risk", "Custom"]
        for scenario_name in scenario_names:
            if scenario_name not in self.brokers:
                try:
                    self._initialize_scenario_components(scenario_name)
                except Exception as e:
                    logger.warning(f"Failed to initialize components for {scenario_name}: {e}")
        
        scenario_configs = {
            "Conservative": {
                "type": "Conservative",
                "settings": {
                    "dalio": {"enabled": True, "violation_penalty_pct": 0.05},
                    "buffett": {"enabled": True, "minimum_expected_return": 0.20, "violation_penalty_pct": 0.20},
                    "pabrai": {"enabled": True, "cluster_threshold": 4, "position_multiplier": 1.5, "allocation_bonus_pct": 0.05},
                    "oleary": {"enabled": True, "max_hold_days": 60, "min_return_threshold": 0.08},
                    "saylor": {"enabled": False, "sharpe_threshold": 3.0, "extension_days": 15, "min_tier": "S"},
                    "japanese_discipline": {"enabled": True, "rules": {"fixed_round_duration_days": 60, "violation_penalty_pct": 0.25, "penalty_decay_rounds": 15}}
                }
            },
            "Balanced": {
                "type": "Balanced", 
                "settings": {
                    "dalio": {"enabled": True, "violation_penalty_pct": 0.10},
                    "buffett": {"enabled": True, "minimum_expected_return": 0.15, "violation_penalty_pct": 0.15},
                    "pabrai": {"enabled": True, "cluster_threshold": 3, "position_multiplier": 2.0, "allocation_bonus_pct": 0.10},
                    "oleary": {"enabled": True, "max_hold_days": 90, "min_return_threshold": 0.05},
                    "saylor": {"enabled": True, "sharpe_threshold": 2.0, "extension_days": 30, "min_tier": "A"},
                    "japanese_discipline": {"enabled": True, "rules": {"fixed_round_duration_days": 90, "violation_penalty_pct": 0.20, "penalty_decay_rounds": 10}}
                }
            },
            "Aggressive": {
                "type": "Aggressive",
                "settings": {
                    "dalio": {"enabled": True, "violation_penalty_pct": 0.15},
                    "buffett": {"enabled": True, "minimum_expected_return": 0.10, "violation_penalty_pct": 0.10},
                    "pabrai": {"enabled": True, "cluster_threshold": 2, "position_multiplier": 2.5, "allocation_bonus_pct": 0.15},
                    "oleary": {"enabled": True, "max_hold_days": 120, "min_return_threshold": 0.03},
                    "saylor": {"enabled": True, "sharpe_threshold": 1.5, "extension_days": 45, "min_tier": "B"},
                    "japanese_discipline": {"enabled": True, "rules": {"fixed_round_duration_days": 120, "violation_penalty_pct": 0.15, "penalty_decay_rounds": 8}}
                }
            },
            "High-Risk": {
                "type": "High-Risk",
                "settings": {
                    "dalio": {"enabled": False, "violation_penalty_pct": 0.05},
                    "buffett": {"enabled": True, "minimum_expected_return": 0.05, "violation_penalty_pct": 0.05},
                    "pabrai": {"enabled": True, "cluster_threshold": 2, "position_multiplier": 3.0, "allocation_bonus_pct": 0.20},
                    "oleary": {"enabled": False, "max_hold_days": 180, "min_return_threshold": 0.01},
                    "saylor": {"enabled": True, "sharpe_threshold": 1.0, "extension_days": 60, "min_tier": "C"},
                    "japanese_discipline": {"enabled": False, "rules": {"fixed_round_duration_days": 180, "violation_penalty_pct": 0.10, "penalty_decay_rounds": 5}}
                }
            },
            "Custom": {
                "type": "Custom",
                "settings": {
                    "dalio": {"enabled": True, "violation_penalty_pct": 0.10},
                    "buffett": {"enabled": True, "minimum_expected_return": 0.15, "violation_penalty_pct": 0.15},
                    "pabrai": {"enabled": True, "cluster_threshold": 3, "position_multiplier": 2.0, "allocation_bonus_pct": 0.10},
                    "oleary": {"enabled": True, "max_hold_days": 90, "min_return_threshold": 0.05},
                    "saylor": {"enabled": True, "sharpe_threshold": 2.0, "extension_days": 30, "min_tier": "A"},
                    "japanese_discipline": {"enabled": True, "rules": {"fixed_round_duration_days": 90, "violation_penalty_pct": 0.20, "penalty_decay_rounds": 10}}
                }
            }
        }
        
        for scenario_name, config in scenario_configs.items():
            self._create_scenario(scenario_name, config)
        
        logger.info(f"Initialized {len(scenario_configs)} trading scenarios")
    
    def _create_scenario(self, scenario_name: str, config: Dict):
        """Create a new scenario in the database."""
        try:
            # Check if scenario already exists
            existing = self.db.query(Scenario).filter(Scenario.scenario_name == scenario_name).first()
            if existing:
                logger.info(f"Scenario {scenario_name} already exists, skipping creation")
                return
            
            # Create new scenario
            scenario = Scenario(
                scenario_name=scenario_name,
                scenario_type=config["type"],
                philosophy_settings=config["settings"],
                initial_capital=100000.0,
                current_capital=100000.0,
                is_active=True
            )
            
            self.db.add(scenario)
            self.db.commit()
            
            # Initialize components for this scenario
            self._initialize_scenario_components(scenario_name)
            
            logger.info(f"Created scenario: {scenario_name}")
            
        except Exception as e:
            logger.error(f"Failed to create scenario {scenario_name}: {e}")
            self.db.rollback()
            raise
    
    def _initialize_scenario_components(self, scenario_name: str):
        """Initialize trading components for a specific scenario."""
        try:
            # Create separate paper broker for this scenario
            broker = PaperBroker()
            broker.connect()
            self.brokers[scenario_name] = broker
            
            # Create order manager
            order_manager = OrderManager(self.db, broker)
            self.order_managers[scenario_name] = order_manager
            
            # Create cycle manager
            cycle_manager = CycleManager(self.db)
            self.cycle_managers[scenario_name] = cycle_manager
            
            # Create cycle allocator
            cycle_allocator = CycleAllocator(self.db)
            self.cycle_allocators[scenario_name] = cycle_allocator
            
            # Create philosophy engine (settings are loaded from config file)
            philosophy_engine = PhilosophyEngine(self.db)
            self.philosophy_engines[scenario_name] = philosophy_engine
            
            logger.info(f"Initialized components for scenario: {scenario_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize components for scenario {scenario_name}: {e}")
            raise
    
    def execute_scenario_allocation(self, scenario_name: str) -> Dict:
        """Execute allocation for a specific scenario."""
        try:
            if scenario_name not in self.brokers:
                raise ValueError(f"Scenario {scenario_name} not initialized")
            
            # Get scenario components
            broker = self.brokers[scenario_name]
            order_manager = self.order_managers[scenario_name]
            cycle_manager = self.cycle_managers[scenario_name]
            cycle_allocator = self.cycle_allocators[scenario_name]
            philosophy_engine = self.philosophy_engines[scenario_name]
            
            # Get scenario database record
            scenario = self.db.query(Scenario).filter(Scenario.scenario_name == scenario_name).first()
            if not scenario:
                raise ValueError(f"Scenario {scenario_name} not found in database")
            
            # Get active cycle for this scenario
            active_cycle = cycle_manager.get_active_cycle()
            if not active_cycle:
                active_cycle = cycle_manager.create_new_cycle()
            
            # Get portfolio value
            portfolio_value = broker.get_account_value()
            
            # Get all active signals (philosophy filtering will be applied during allocation)
            filtered_signals = self.db.query(Signal).filter(Signal.status == 'ACTIVE').all()
            
            # Allocate capital using cycle system
            decisions = cycle_allocator.allocate_for_cycle(active_cycle, portfolio_value)
            
            if not decisions:
                return {"allocated": 0, "scenario": scenario_name}
            
            # Execute decisions with scenario-specific position management
            executed = 0
            closed_positions = 0
            
            for decision in decisions:
                try:
                    symbol = decision['symbol']
                    
                    # Check for existing positions in this scenario
                    existing_positions = self.db.query(ScenarioPosition).filter(
                        ScenarioPosition.scenario_id == scenario.id,
                        ScenarioPosition.symbol == symbol,
                        ScenarioPosition.status == 'OPEN'
                    ).all()
                    
                    # Close existing positions before opening new one
                    for existing_pos in existing_positions:
                        logger.info(f"Closing existing position for {symbol} in scenario {scenario_name}")
                        
                        # Create exit order
                        exit_order = order_manager.create_exit_order(existing_pos, reason='REALLOCATION')
                        
                        # Execute exit order
                        exit_result = order_manager.execute_order(exit_order)
                        
                        if exit_result:
                            closed_positions += 1
                            # Update scenario position
                            existing_pos.status = 'CLOSED'
                            existing_pos.exit_date = datetime.utcnow()
                            existing_pos.exit_price = exit_order.filled_avg_price or existing_pos.entry_price
                            existing_pos.realized_pnl = float(existing_pos.exit_price - existing_pos.entry_price) * float(existing_pos.shares)
                    
                    # Create new position
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
                    position_id = f"{scenario_name}_{symbol}_{timestamp}"
                    
                    # Create order using allocation format
                    allocation = {
                        'symbol': symbol,
                        'direction': decision['direction'],
                        'shares': decision['shares']
                    }
                    
                    order = order_manager.create_entry_order(allocation, position_id)
                    
                    # Execute order
                    result = order_manager.execute_order(order)
                    
                    if result:
                        # Create scenario position
                        scenario_position = ScenarioPosition(
                            scenario_id=scenario.id,
                            position_id=position_id,
                            symbol=symbol,
                            direction=decision['direction'],
                            entry_date=datetime.utcnow(),
                            entry_price=order.filled_avg_price or decision['target_price'],
                            shares=decision['shares'],
                            entry_value=float(decision['shares']) * float(order.filled_avg_price or decision['target_price']),
                            conviction_tier=decision['conviction_tier'],
                            status='OPEN'
                        )
                        
                        self.db.add(scenario_position)
                        executed += 1
                        
                        logger.info(f"Executed position for {scenario_name}: {symbol} {decision['shares']} shares")
                
                except Exception as e:
                    logger.error(f"Failed to execute decision for {decision['symbol']} in scenario {scenario_name}: {e}")
                    continue
            
            # Update scenario performance
            self._update_scenario_performance(scenario_name)
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Scenario {scenario_name} allocation complete: {executed} positions executed, {closed_positions} positions closed")
            
            return {
                "allocated": executed,
                "closed": closed_positions,
                "scenario": scenario_name,
                "total_decisions": len(decisions),
                "portfolio_value": float(portfolio_value)
            }
            
        except Exception as e:
            logger.error(f"Scenario {scenario_name} allocation failed: {e}")
            self.db.rollback()
            raise
    
    def _update_scenario_performance(self, scenario_name: str):
        """Update performance metrics for a scenario."""
        try:
            scenario = self.db.query(Scenario).filter(Scenario.scenario_name == scenario_name).first()
            if not scenario:
                return
            
            # Calculate current capital
            broker = self.brokers[scenario_name]
            current_capital = broker.get_account_value()
            
            # Calculate P&L
            total_pnl = current_capital - scenario.initial_capital
            total_return_pct = (total_pnl / scenario.initial_capital) * 100
            
            # Update scenario
            scenario.current_capital = current_capital
            scenario.total_pnl = total_pnl
            scenario.total_return_pct = total_return_pct
            scenario.last_updated = datetime.utcnow()
            
            # Calculate trade statistics
            positions = self.db.query(ScenarioPosition).filter(
                ScenarioPosition.scenario_id == scenario.id
            ).all()
            
            closed_positions = [p for p in positions if p.status == 'CLOSED']
            total_trades = len(closed_positions)
            winning_trades = len([p for p in closed_positions if p.realized_pnl > 0])
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            scenario.total_trades = total_trades
            scenario.winning_trades = winning_trades
            scenario.losing_trades = losing_trades
            scenario.win_rate = win_rate
            
            logger.info(f"Updated performance for scenario {scenario_name}: {total_return_pct:.2f}% return, {win_rate:.1f}% win rate")
            
        except Exception as e:
            logger.error(f"Failed to update performance for scenario {scenario_name}: {e}")
    
    def get_scenario_performance(self) -> List[Dict]:
        """Get performance summary for all scenarios."""
        try:
            scenarios = self.db.query(Scenario).filter(Scenario.is_active == True).all()
            
            performance_data = []
            for scenario in scenarios:
                performance_data.append({
                    "scenario_name": scenario.scenario_name,
                    "scenario_type": scenario.scenario_type,
                    "current_capital": scenario.current_capital,
                    "total_pnl": scenario.total_pnl,
                    "total_return_pct": scenario.total_return_pct,
                    "total_trades": scenario.total_trades,
                    "win_rate": scenario.win_rate,
                    "max_drawdown": scenario.max_drawdown,
                    "sharpe_ratio": scenario.sharpe_ratio,
                    "last_updated": scenario.last_updated
                })
            
            return performance_data
            
        except Exception as e:
            logger.error(f"Failed to get scenario performance: {e}")
            return []
    
    def cleanup(self):
        """Clean up resources."""
        for broker in self.brokers.values():
            try:
                broker.disconnect()
            except:
                pass
        
        logger.info("Scenario manager cleanup complete")
