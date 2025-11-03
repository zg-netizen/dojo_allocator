"""Backfill historical data for testing.
Fetches past signals and scores them."""
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.models.base import SessionLocal
from src.models.signals import Signal
from src.data.stock_act import StockActFetcher
from src.core.signal_scorer import SignalScorer
import uuid

def backfill_signals(days: int = 90):
    """Backfill signals from past N days.
    
    Args:
        days: How many days back to fetch
    """
    db = SessionLocal()
    print("🥋 Dojo Allocator - Data Backfill")
    print("=" * 50)
    print(f"Fetching signals from past {days} days...")
    
    fetcher = StockActFetcher()
    trades = fetcher.fetch_recent_trades()
    signals_data = fetcher.transform_to_signal_format(trades)
    
    print(f"\n✓ Found {len(signals_data)} trade signals")
    
    if not signals_data:
        print("\nℹ No signals found. This is normal if:")
        print("  - House Stock Watcher API is unavailable")
        print("  - No trades in the lookback period")
        print("  - Network connectivity issues")
        db.close()
        return
    
    print("\nScoring signals...")
    scorer = SignalScorer(db)
    
    added_count = 0
    duplicate_count = 0
    rejected_count = 0
    
    for signal_data in signals_data:
        existing = db.query(Signal).filter(
            Signal.symbol == signal_data['symbol'],
            Signal.source == signal_data['source'],
            Signal.transaction_date == signal_data['transaction_date']
        ).first()
        
        if existing:
            duplicate_count += 1
            continue
        
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
        
        similar_signals = db.query(Signal).filter(
            Signal.symbol == signal.symbol,
            Signal.direction == signal.direction,
            Signal.status == 'ACTIVE'
        ).all()
        
        filer_history = None
        
        try:
            factors = scorer.score_signal(
                signal={
                    'signal_id': signal_id,
                    'filing_date': signal_data['filing_date'],
                    'transaction_value': signal_data['transaction_value'],
                    'symbol': signal_data['symbol'],
                    'filer_cik': signal_data.get('filer_cik')
                },
                similar_signals=similar_signals,
                filer_history=filer_history
            )
            
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
                rejected_count += 1
            else:
                signal.status = 'ACTIVE'
            
            db.add(signal)
            added_count += 1
            print(f"  ✓ {signal.symbol} - Tier {tier} - Score {total_score:.3f}")
            
        except Exception as e:
            print(f"  ✗ Error scoring {signal_data['symbol']}: {e}")
            continue
    
    db.commit()
    db.close()
    
    print("\n" + "=" * 50)
    print("✅ Backfill complete!")
    print(f"\nResults:")
    print(f"  Added: {added_count} signals")
    print(f"  Duplicates: {duplicate_count}")
    print(f"  Rejected: {rejected_count}")
    print(f"\nNext step: View signals in dashboard at http://localhost:8501")

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    backfill_signals(days)
