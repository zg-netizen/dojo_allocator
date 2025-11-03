from src.models.base import SessionLocal
from src.models.signals import Signal
from src.models.positions import Position
from src.core.allocator import Allocator
from src.core.round_manager import RoundManager
from src.execution.paper_broker import PaperBroker
from src.execution.order_manager import OrderManager
from datetime import datetime
from decimal import Decimal

db = SessionLocal()
allocator = Allocator()
round_manager = RoundManager(db)
broker = PaperBroker(starting_cash=Decimal(100000))
broker.connect()
order_manager = OrderManager(db, broker)

signals = db.query(Signal).filter(Signal.status == 'ACTIVE').all()
print(f'Found {len(signals)} signals')

decisions = allocator.allocate_capital(
    signals=signals,
    current_portfolio_value=Decimal(100000),
    open_positions=[],
    allocation_power=1.0
)

print(f'Decisions: {len(decisions)}')

for d in decisions:
    s = next(x for x in signals if x.signal_id == d.signal_id)
    rp = round_manager.create_round(signal=s, allocation=d.__dict__)
    
    pos = Position(
        position_id=f'POS_{d.symbol}_{int(datetime.utcnow().timestamp())}',
        symbol=d.symbol,
        direction=d.direction,
        shares=d.shares,
        entry_date=datetime.utcnow(),
        conviction_tier=d.conviction_tier,
        philosophy_applied=d.philosophy_applied,
        source_signals=[d.signal_id],
        round_start=rp['round_start'],
        round_expiry=rp['round_expiry'],
        status='PENDING'
    )
    db.add(pos)
    db.flush()
    
    order = order_manager.create_entry_order(allocation=d.__dict__, position_id=pos.position_id)
    ok = order_manager.execute_order(order)
    
    if ok:
        db.refresh(pos)
        print(f'+ {pos.symbol}: {pos.shares} shares')

db.commit()
broker.disconnect()
print('Done')
