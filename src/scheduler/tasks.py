"""
Celery background tasks.
"""
from celery import Task
from src.scheduler.celery_app import app
from src.models.base import SessionLocal
from src.models.signals import Signal
from src.models.positions import Position
from src.data.stock_act import StockActFetcher
from src.data.transformers import SignalTransformer
from src.core.signal_scorer import SignalScorer
from src.core.allocator import Allocator
from src.core.round_manager import RoundManager
from src.core.scenario_manager import ScenarioManager
from src.execution.paper_broker import PaperBroker
from src.execution.order_manager import OrderManager
from src.utils.logging import get_logger
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import yfinance as yf

logger = get_logger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@app.task(base=DatabaseTask, bind=True)
def ingest_all_data(self):
    """
    Daily task: Ingest data from all sources.
    Runs at 6 AM UTC.
    """
    logger.info("Starting data ingestion")
    
    db = self.db
    
    try:
        # Fetch congressional trades
        fetcher = StockActFetcher()
        trades = fetcher.fetch_recent_trades()
        signals_data = fetcher.transform_to_signal_format(trades)
        
        logger.info(f"Fetched {len(signals_data)} signals from STOCK Act")
        # Fetch OpenInsider congressional trades
        from src.data.openinsider import OpenInsiderFetcher
        oi_fetcher = OpenInsiderFetcher()
        oi_trades = oi_fetcher.fetch_congressional_trades(limit=100)
        oi_signals = oi_fetcher.transform_to_signal_format(oi_trades, source='congressional')
        logger.info(f"OpenInsider: {len(oi_signals)} congressional signals")
        
        # Fetch OpenInsider insider purchases (separate from Form 4)
        insider_trades = oi_fetcher.fetch_recent_buys(limit=50)
        insider_signals = oi_fetcher.transform_to_signal_format(insider_trades, source='insider')
        logger.info(f"OpenInsider: {len(insider_signals)} insider signals")
        
        # Fetch SEC EDGAR Form 4 insider trades
        from src.data.sec_edgar import SECEdgarFetcher
        sec_fetcher = SECEdgarFetcher()
        form4_filings = sec_fetcher.fetch_recent_form4(limit=50)
        form4_signals = sec_fetcher.transform_form4_to_signal_format(form4_filings)
        logger.info(f"SEC EDGAR: {len(form4_signals)} Form 4 signals")
        
        # Combine all signals
        signals_data = signals_data + oi_signals + insider_signals + form4_signals        

        # Apply quality filters
        from src.core.signal_quality_filter import SignalQualityFilter
        quality_filter = SignalQualityFilter()
        
        filtered_signals = []
        rejected_count = 0
        
        for signal_data in signals_data:
            passes_filter, rejection_reason = quality_filter.apply_quality_filters(signal_data)
            
            if passes_filter:
                filtered_signals.append(signal_data)
            else:
                rejected_count += 1
                logger.info(f"Rejected signal: {signal_data.get('symbol', 'N/A')} - {rejection_reason}")
        
        logger.info(f"Quality filtering: {len(signals_data)} total, {len(filtered_signals)} passed, {rejected_count} rejected")
        
        # Use filtered signals for database storage
        signals_data = filtered_signals
        
        added = 0
        duplicates = 0
        
        for signal_data in signals_data:
            # Check for duplicates
            existing = db.query(Signal).filter(
                Signal.symbol == signal_data['symbol'],
                Signal.source == signal_data['source'],
                Signal.transaction_date == signal_data['transaction_date']
            ).first()
            
            if existing:
                duplicates += 1
                continue
            
            # Create signal
            signal_id = f"{signal_data['source']}_{signal_data['symbol']}_{uuid.uuid4().hex[:8]}"
            
            signal = Signal(
                signal_id=signal_id,
                source=signal_data['source'],
                symbol=signal_data['symbol'],
                direction=signal_data['direction'],
                filer_name=signal_data['filer_name'],
                transaction_date=signal_data['transaction_date'],
                filing_date=signal_data['filing_date'],
                transaction_value=signal_data['transaction_value'],
                status='PENDING',
                raw_data=signal_data.get('raw_data', {})
            )
            
            db.add(signal)
            added += 1
        
        db.commit()
        
        logger.info(f"Data ingestion complete: {added} added, {duplicates} duplicates")
        return {"added": added, "duplicates": duplicates}
        
    except Exception as e:
        logger.error(f"Data ingestion failed: {e}")
        db.rollback()
        raise


@app.task(base=DatabaseTask, bind=True)
def score_all_signals(self):
    """
    Daily task: Score all pending signals.
    Runs at 7 AM UTC.
    """
    logger.info("Starting signal scoring")
    
    db = self.db
    scorer = SignalScorer(db)
    
    try:
        # Get all pending signals
        pending_signals = db.query(Signal).filter(
            Signal.status == 'PENDING'
        ).all()
        
        logger.info(f"Scoring {len(pending_signals)} pending signals")
        
        scored = 0
        rejected = 0
        
        for signal in pending_signals:
            # Find similar signals
            similar = db.query(Signal).filter(
                Signal.symbol == signal.symbol,
                Signal.direction == signal.direction,
                Signal.status == 'ACTIVE'
            ).all()
            
            # Score signal using quality filter enhancements
            from src.core.signal_quality_filter import SignalQualityFilter
            quality_filter = SignalQualityFilter()
            
            # Convert signal to dict for quality filter
            signal_dict = {
                'source': signal.source,
                'symbol': signal.symbol,
                'direction': signal.direction,
                'filer_name': signal.filer_name,
                'title': getattr(signal, 'title', None),
                'transaction_code': getattr(signal, 'transaction_code', None),
                'price': float(signal.price) if signal.price else None,
                'transaction_value': float(signal.transaction_value) if signal.transaction_value else None,
                'filing_date': signal.filing_date
            }
            
            # Calculate enhanced scores
            recency_score = quality_filter.calculate_recency_score(signal_dict)
            insider_quality_mult = quality_filter.get_insider_quality_multiplier(signal_dict)
            consensus_score = quality_filter.calculate_consensus_score(signal_dict, similar)
            
            # Score signal
            factors = scorer.score_signal(
                signal={
                    'signal_id': signal.signal_id,
                    'filing_date': signal.filing_date,
                    'transaction_value': signal.transaction_value,
                    'symbol': signal.symbol,
                    'filer_cik': None
                },
                similar_signals=similar,
                filer_history=None
            )
            
            # Override recency and consensus with quality filter values
            factors.recency_score = recency_score
            factors.consensus_score = consensus_score
            
            # Apply insider quality multiplier to competence score
            factors.competence_score = min(1.0, factors.competence_score * insider_quality_mult)
            
            # Update signal
            signal.recency_score = factors.recency_score
            signal.size_score = factors.size_score
            signal.competence_score = factors.competence_score
            signal.consensus_score = factors.consensus_score
            signal.regime_score = factors.regime_score
            
            total_score = scorer.calculate_total_score(factors)
            signal.total_score = total_score
            
            tier = scorer.assign_tier(total_score)
            signal.conviction_tier = tier
            
            if tier == 'REJECT':
                signal.status = 'REJECTED'
                rejected += 1
            else:
                signal.status = 'ACTIVE'
                scored += 1
        
        db.commit()
        
        logger.info(f"Signal scoring complete: {scored} scored, {rejected} rejected")
        return {"scored": scored, "rejected": rejected}
        
    except Exception as e:
        logger.error(f"Signal scoring failed: {e}")
        db.rollback()
        raise


@app.task(base=DatabaseTask, bind=True)
def allocate_and_execute(self):
    """
    Daily task: Allocate capital and execute trades using 90-day cycle system.
    Runs at 8 AM UTC.
    """
    logger.info("Starting cycle-based capital allocation")
    
    db = self.db
    
    try:
        # Initialize cycle manager
        from src.core.cycle_manager import CycleManager
        from src.core.cycle_allocator import CycleAllocator
        
        cycle_manager = CycleManager(db)
        cycle_allocator = CycleAllocator(db)
        
        # Get or create active cycle
        active_cycle = cycle_manager.get_active_cycle()
        if not active_cycle:
            logger.info("No active cycle found, creating new cycle")
            active_cycle = cycle_manager.create_new_cycle()
        
        # Check if current cycle should be completed
        if cycle_manager.check_cycle_completion(active_cycle):
            logger.info(f"Cycle {active_cycle.cycle_id} should be completed")
            completion_result = cycle_manager.complete_cycle(active_cycle)
            logger.info(f"Completed cycle: {completion_result}")
            
            # Create new cycle
            active_cycle = cycle_manager.create_new_cycle()
            logger.info(f"Created new cycle: {active_cycle.cycle_id}")
        
        # Get open positions
        open_positions = db.query(Position).filter(
            Position.status == 'OPEN'
        ).all()
        
        # Initialize components
        allocator = Allocator()
        broker = PaperBroker()
        broker.connect()
        
        # Get current portfolio value
        portfolio_value = broker.get_account_value()
        
        # Get allocation power (default to 1.0)
        allocation_power = 1.0
        
        # Allocate capital using cycle system
        decisions = cycle_allocator.allocate_for_cycle(active_cycle, portfolio_value)
        
        logger.info(f"Generated {len(decisions)} cycle allocation decisions")
        
        if not decisions:
            logger.info("No allocation decisions generated")
            return {"allocated": 0, "cycle_id": active_cycle.cycle_id}
        
        # Execute decisions with position management
        order_manager = OrderManager(db, broker)
        round_manager = RoundManager(db)
        
        executed = 0
        closed_positions = 0
        
        for decision in decisions:
            try:
                symbol = decision['symbol']
                
                # Check for existing positions in this symbol
                existing_positions = db.query(Position).filter(
                    Position.symbol == symbol,
                    Position.status == 'OPEN'
                ).all()
                
                # Close existing positions before opening new one
                for existing_pos in existing_positions:
                    logger.info(f"Closing existing position for {symbol}: {existing_pos.position_id}")
                    
                    # Create exit order
                    exit_order = order_manager.create_exit_order(existing_pos, reason='REALLOCATION')
                    
                    # Execute exit order
                    exit_result = order_manager.execute_order(exit_order)
                    
                    if exit_result:
                        closed_positions += 1
                        logger.info(f"Closed position {existing_pos.position_id} for reallocation")
                    else:
                        logger.warning(f"Failed to close position {existing_pos.position_id}")
                
                # Create unique position ID with timestamp and counter
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
                position_id = f"{symbol}_{timestamp}"
                
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
                    # Create position with cycle ID
                    position = Position(
                        position_id=position_id,
                        symbol=symbol,
                        direction=decision['direction'],
                        entry_date=datetime.utcnow(),
                        entry_price=order.filled_avg_price or decision['target_price'],
                        shares=decision['shares'],
                        entry_value=float(decision['shares']) * float(order.filled_avg_price or decision['target_price']),
                        conviction_tier=decision['conviction_tier'],
                        cycle_id=active_cycle.cycle_id,
                        status='OPEN',
                        round_start=datetime.utcnow(),
                        round_expiry=datetime.utcnow() + timedelta(days=90)
                    )
                    
                    db.add(position)
                    executed += 1
                    
                    logger.info(f"Executed position: {decision['symbol']} {decision['shares']} shares @ ${order.filled_avg_price or decision['target_price']}")
                
            except Exception as e:
                logger.error(f"Failed to execute decision for {decision['symbol']}: {e}")
                continue
        
        # Update cycle performance
        cycle_manager.update_cycle_performance(active_cycle)
        
        # Commit all changes
        db.commit()
        
        logger.info(f"Cycle allocation complete: {executed} positions executed, {closed_positions} positions closed")
        
        return {
            "allocated": executed,
            "closed": closed_positions,
            "cycle_id": active_cycle.cycle_id,
            "total_decisions": len(decisions),
            "portfolio_value": float(portfolio_value)
        }
        
    except Exception as e:
        logger.error(f"Cycle allocation failed: {e}")
        db.rollback()
        raise


@app.task(base=DatabaseTask, bind=True)
def cleanup_duplicate_positions(self):
    """
    Emergency task: Close duplicate positions for the same symbol.
    This addresses the current issue where multiple positions exist for the same symbol.
    """
    logger.info("Starting duplicate position cleanup")
    
    db = self.db
    
    try:
        # Find symbols with multiple open positions
        from sqlalchemy import func
        
        duplicate_symbols = db.query(Position.symbol, func.count(Position.position_id)).filter(
            Position.status == 'OPEN'
        ).group_by(Position.symbol).having(func.count(Position.position_id) > 1).all()
        
        logger.info(f"Found {len(duplicate_symbols)} symbols with duplicate positions")
        
        closed_count = 0
        
        for symbol, count in duplicate_symbols:
            logger.info(f"Cleaning up {count} positions for {symbol}")
            
            # Get all open positions for this symbol, ordered by entry date (keep oldest)
            positions = db.query(Position).filter(
                Position.symbol == symbol,
                Position.status == 'OPEN'
            ).order_by(Position.entry_date.asc()).all()
            
            # Keep the first (oldest) position, close the rest
            positions_to_close = positions[1:]  # Skip the first (oldest) position
            
            for position in positions_to_close:
                logger.info(f"Closing duplicate position: {position.position_id}")
                
                # Mark as closed with reallocation reason
                position.status = 'CLOSED'
                position.exit_date = datetime.utcnow()
                position.exit_price = position.entry_price  # Assume no change for cleanup
                position.realized_pnl = Decimal('0.00')  # No P&L for cleanup
                position.exit_reason = 'DUPLICATE_CLEANUP'
                
                closed_count += 1
        
        db.commit()
        
        logger.info(f"Duplicate cleanup complete: {closed_count} positions closed")
        
        return {
            "duplicate_symbols": len(duplicate_symbols),
            "positions_closed": closed_count
        }
        
    except Exception as e:
        logger.error(f"Duplicate cleanup failed: {e}")
        db.rollback()
        raise


@app.task(base=DatabaseTask, bind=True)
def check_position_expiry(self):
    """
    Hourly task: Check for expired positions and close them.
    """
    logger.info("Checking position expiry")
    
    db = self.db
    round_manager = RoundManager(db)
    
    try:
        # Force close expired positions
        expired = round_manager.force_close_expired()
        
        if expired:
            # Execute exit orders
            broker = PaperBroker()
            broker.connect()
            order_manager = OrderManager(db, broker)
            
            for position in expired:
                exit_order = order_manager.create_exit_order(
                    position=position,
                    reason='EXPIRY'
                )
                order_manager.execute_order(exit_order)
            
            broker.disconnect()
        
        logger.info(f"Position expiry check complete: {len(expired)} closed")
        return {"closed": len(expired)}
        
    except Exception as e:
        logger.error(f"Position expiry check failed: {e}")
        raise


@app.task(base=DatabaseTask, bind=True)
def execute_review_cycle(self):
    """
    Daily task: Execute review cycle for tier escalation confirmation.
    Runs at 9 AM UTC (after signal scoring and allocation).
    
    Implements Tier Escalation Confirmation rule:
    - Higher-tier signal must persist for 2 consecutive review cycles
    - Prevents oscillation between tiers
    - Executes close-and-reopen for confirmed escalations
    """
    logger.info("Starting review cycle execution")
    
    db = self.db
    
    try:
        # Initialize review cycle manager
        review_manager = ReviewCycleManager(db)
        
        # Execute review cycle
        result = review_manager.execute_review_cycle()
        
        logger.info(
            "Review cycle completed",
            potential_escalations=result["potential_escalations"],
            executed_escalations=result["executed_escalations"]
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Review cycle execution failed: {e}")
        db.rollback()
        raise


@app.task(base=DatabaseTask, bind=True)
def end_of_day_reconciliation(self):
    """
    Daily task: End-of-day reconciliation and reporting.
    Runs at 10 PM UTC.
    """
    logger.info("Starting end-of-day reconciliation")
    
    db = self.db
    
    try:
        # Count signals
        total_signals = db.query(Signal).count()
        active_signals = db.query(Signal).filter(Signal.status == 'ACTIVE').count()
        
        # Count positions
        open_positions = db.query(Position).filter(Position.status == 'OPEN').count()
        closed_today = db.query(Position).filter(
            Position.status == 'CLOSED',
            Position.exit_date >= datetime.utcnow().date()
        ).count()
        
        logger.info(
            f"EOD Summary: {total_signals} signals ({active_signals} active), "
            f"{open_positions} open positions, {closed_today} closed today"
        )
        
        return {
            "total_signals": total_signals,
            "active_signals": active_signals,
            "open_positions": open_positions,
            "closed_today": closed_today
        }
        
    except Exception as e:
        logger.error(f"EOD reconciliation failed: {e}")
        raise


@app.task(base=DatabaseTask, bind=True)
def execute_parallel_scenarios(self):
    """
    Execute all 5 scenarios in parallel with different philosophy settings.
    Each scenario runs independently with its own paper trading environment.
    """
    logger.info("Starting parallel scenario execution")
    
    db = self.db
    
    try:
        # Initialize scenario manager
        scenario_manager = ScenarioManager(db)
        
        # Initialize scenarios if they don't exist
        scenario_manager.initialize_scenarios()
        
        # Execute all scenarios
        results = {}
        scenario_names = ["Conservative", "Balanced", "Aggressive", "High-Risk", "Custom"]
        
        for scenario_name in scenario_names:
            try:
                result = scenario_manager.execute_scenario_allocation(scenario_name)
                results[scenario_name] = result
                logger.info(f"Scenario {scenario_name} completed: {result['allocated']} positions allocated")
            except Exception as e:
                logger.error(f"Scenario {scenario_name} failed: {e}")
                results[scenario_name] = {"error": str(e), "allocated": 0}
        
        # Get performance summary
        performance_data = scenario_manager.get_scenario_performance()
        
        # Cleanup
        scenario_manager.cleanup()
        
        logger.info(f"Parallel scenario execution complete: {len(results)} scenarios processed")
        
        return {
            "scenario_results": results,
            "performance_summary": performance_data,
            "total_scenarios": len(scenario_names),
            "successful_scenarios": len([r for r in results.values() if "error" not in r])
        }
        
    except Exception as e:
        logger.error(f"Parallel scenario execution failed: {e}")
        db.rollback()
        raise


@app.task(base=DatabaseTask, bind=True)
def update_scenario_unrealized(self):
    """
    Live task: Update scenario current_capital/total_pnl/total_return_pct using
    unrealized P&L from scenario_positions and live prices.

    Runs frequently (e.g., every 5 minutes via beat). Safe if prices fail; it will skip gracefully.
    """
    logger.info("Updating scenario unrealized performance from live prices")

    db = self.db

    try:
        from sqlalchemy import func
        from src.models.scenarios import Scenario, ScenarioPosition

        scenarios = db.query(Scenario).filter(Scenario.is_active == True).all()

        # Build symbol set per scenario
        for scenario in scenarios:
            open_positions = db.query(ScenarioPosition).filter(
                ScenarioPosition.scenario_id == scenario.id,
                ScenarioPosition.status == 'OPEN'
            ).all()

            if not open_positions:
                # No open positions: current capital = initial + realized from closed
                realized = db.query(func.coalesce(func.sum(ScenarioPosition.realized_pnl), 0.0)).filter(
                    ScenarioPosition.scenario_id == scenario.id,
                    ScenarioPosition.status == 'CLOSED'
                ).scalar() or 0.0

                current_capital = float(scenario.initial_capital) + float(realized)
                total_pnl = current_capital - float(scenario.initial_capital)
                total_return_pct = (total_pnl / float(scenario.initial_capital) * 100.0) if scenario.initial_capital else 0.0

                scenario.current_capital = current_capital
                scenario.total_pnl = total_pnl
                scenario.total_return_pct = total_return_pct
                scenario.last_updated = datetime.utcnow()
                continue

            # Fetch live prices for unique symbols
            symbols = sorted({p.symbol for p in open_positions})
            prices: dict[str, float] = {}

            for sym in symbols:
                try:
                    t = yf.Ticker(sym)
                    price = None
                    try:
                        intraday = t.history(period="1d", interval="1m")
                        if not intraday.empty and "Close" in intraday.columns:
                            price = float(intraday["Close"].dropna().iloc[-1])
                    except Exception:
                        pass
                    if price is None:
                        fi = getattr(t, "fast_info", None)
                        if fi and getattr(fi, "last_price", None):
                            price = float(fi.last_price)
                    if price is None:
                        daily = t.history(period="1d")
                        if not daily.empty:
                            price = float(daily["Close"].iloc[-1])
                    if price is not None:
                        prices[sym] = price
                except Exception:
                    continue

            # Compute unrealized P&L (with re-basing to live price if legacy synthetic entry prices are detected)
            unrealized = 0.0
            invested = 0.0
            for p in open_positions:
                cur = prices.get(p.symbol)
                # If we cannot fetch a current price, skip from unrealized but still count invested by entry
                baseline_entry_price = float(p.entry_price)
                if cur is not None:
                    # Detect obviously synthetic entry prices (e.g., off by >3x current)
                    try:
                        ratio = abs(baseline_entry_price) / max(abs(cur), 1e-9)
                    except Exception:
                        ratio = 1.0
                    if ratio > 3.0:
                        # Re-base: align entry to live price so unrealized starts at 0 going forward
                        p.entry_price = float(cur)
                        p.entry_value = float(p.shares) * float(cur)
                        baseline_entry_price = float(cur)
                invested += float(p.shares) * baseline_entry_price
                if cur is None:
                    continue
                delta = (cur - baseline_entry_price) * float(p.shares)
                if (p.direction or '').upper() == 'SHORT':
                    delta = -delta
                unrealized += delta

            realized_closed = db.query(func.coalesce(func.sum(ScenarioPosition.realized_pnl), 0.0)).filter(
                ScenarioPosition.scenario_id == scenario.id,
                ScenarioPosition.status == 'CLOSED'
            ).scalar() or 0.0

            total_pnl = float(realized_closed) + float(unrealized)
            current_capital = float(scenario.initial_capital) + total_pnl
            total_return_pct = (total_pnl / float(scenario.initial_capital) * 100.0) if scenario.initial_capital else 0.0

            scenario.current_capital = current_capital
            scenario.total_pnl = total_pnl
            scenario.total_return_pct = total_return_pct
            scenario.last_updated = datetime.utcnow()

        db.commit()
        logger.info("Scenario unrealized performance updated")
        return {"updated": len(scenarios)}

    except Exception as e:
        logger.error(f"Scenario unrealized update failed: {e}")
        db.rollback()
        raise
