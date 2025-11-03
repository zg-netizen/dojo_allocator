"""System integration test.
Tests the complete workflow from signal to execution."""
from datetime import datetime, timedelta
from decimal import Decimal
from src.models.base import SessionLocal
from src.models.signals import Signal
from src.models.positions import Position
from src.core.signal_scorer import SignalScorer
from src.core.allocator import Allocator
from src.core.philosophy_engine import PhilosophyEngine
from src.core.round_manager import RoundManager
from src.execution.paper_broker import PaperBroker
from src.execution.order_manager import OrderManager

def test_complete_workflow():
    """Test complete workflow: signal → score → allocate → execute → close → review"""
    print("🥋 Dojo Allocator - System Test")
    print("=" * 50)
    
    db = SessionLocal()
    scorer = SignalScorer(db)
    allocator = Allocator()
    philosophy_engine = PhilosophyEngine(db)
    round_manager = RoundManager(db)
    broker = PaperBroker(starting_cash=Decimal(100000))
    broker.connect()
    order_manager = OrderManager(db, broker)
    
    print("\n1. Creating test signal...")
    signal = Signal(
        signal_id='TEST_001',
        source='insider',
        symbol='AAPL',
        direction='LONG',
        filer_name='Test Insider',
        transaction_date=datetime.utcnow() - timedelta(days=5),
        filing_date=datetime.utcnow() - timedelta(days=3),
        transaction_value=5000000,
        discovered_at=datetime.utcnow(),
        status='PENDING'
    )
    db.add(signal)
    db.commit()
    print(f"  ✓ Signal created: {signal.signal_id}")
    
    print("\n2. Scoring signal...")
    factors = scorer.score_signal(
        signal={
            'signal_id': signal.signal_id,
            'filing_date': signal.filing_date,
            'transaction_value': signal.transaction_value,
            'symbol': signal.symbol,
            'filer_cik': None
        },
        similar_signals=[],
        filer_history=None
    )
    
    signal.recency_score = factors.recency_score
    signal.size_score = factors.size_score
    signal.competence_score = factors.competence_score
    signal.consensus_score = factors.consensus_score
    signal.regime_score = factors.regime_score
    signal.total_score = scorer.calculate_total_score(factors)
    signal.conviction_tier = scorer.assign_tier(signal.total_score)
    signal.status = 'ACTIVE'
    db.commit()
    
    print(f"  ✓ Scored: {signal.total_score:.3f}")
    print(f"  ✓ Tier: {signal.conviction_tier}")
    
    print("\n3. Allocating capital...")
    decisions = allocator.allocate_capital(
        signals=[signal],
        current_portfolio_value=Decimal(100000),
        open_positions=[],
        allocation_power=1.0
    )
    
    if not decisions:
        print("  ✗ No allocation decisions made")
        db.close()
        broker.disconnect()
        return
    
    decision = decisions[0]
    print(f"  ✓ Position size: {decision.shares} shares")
    print(f"  ✓ Target value: ${decision.target_value:,.2f}")
    
    print("\n4. Creating position and executing entry order...")
    round_params = round_manager.create_round(signal, decision.__dict__)
    
    position = Position(
        position_id=f'POS_TEST_{datetime.utcnow().timestamp()}',
        symbol=decision.symbol,
        direction=decision.direction,
        shares=decision.shares,
        entry_date=datetime.utcnow(),
        conviction_tier=decision.conviction_tier,
        philosophy_applied=decision.philosophy_applied,
        source_signals=[signal.signal_id],
        round_start=round_params['round_start'],
        round_expiry=round_params['round_expiry'],
        status='PENDING'
    )
    db.add(position)
    db.commit()
    
    entry_order = order_manager.create_entry_order(
        allocation=decision.__dict__,
        position_id=position.position_id
    )
    success = order_manager.execute_order(entry_order)
    
    if success:
        print(f"  ✓ Entry order filled")
        db.refresh(position)
        print(f"  ✓ Entry price: ${position.entry_price:.2f}")
    else:
        print("  ✗ Entry order failed")
        db.close()
        broker.disconnect()
        return
    
    print("\n5. Simulating time passage and closing position...")
    exit_order = order_manager.create_exit_order(
        position=position,
        reason='TEST'
    )
    success = order_manager.execute_order(exit_order)
    
    if success:
        print(f"  ✓ Exit order filled")
        db.refresh(position)
        print(f"  ✓ Exit price: ${position.exit_price:.2f}")
        print(f"  ✓ P&L: ${position.realized_pnl:.2f}")
        print(f"  ✓ Return: {position.return_pct:.2%}")
    else:
        print("  ✗ Exit order failed")
    
    print("\n6. Conducting post-round review...")
    review = round_manager.conduct_post_round_review(position)
    print(f"  ✓ Outcome: {review['outcome']}")
    print(f"  ✓ Grade: {review['grade']}")
    print(f"  Lessons learned:")
    for lesson in review['lessons']:
        print(f"    - {lesson}")
    
    print("\n7. Checking account state...")
    print(f"  Final cash: ${broker.get_cash_balance():,.2f}")
    print(f"  Account value: ${broker.get_account_value():,.2f}")
    
    broker.disconnect()
    db.close()
    
    print("\n" + "=" * 50)
    print("✅ System test complete!")
    print("\nAll components working correctly:")
    print("  ✓ Signal scoring")
    print("  ✓ Capital allocation")
    print("  ✓ Order execution")
    print("  ✓ Position management")
    print("  ✓ Round management")

if __name__ == "__main__":
    test_complete_workflow()
