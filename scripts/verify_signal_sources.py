#!/usr/bin/env python3
"""
Signal Source Verification Script

This script verifies which signal sources are currently working and 
provides detailed analysis of the signal pipeline.

Usage:
    python scripts/verify_signal_sources.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy import func
from src.models.base import SessionLocal
from src.models.signals import Signal
from src.data.stock_act import StockActFetcher
from src.data.openinsider import OpenInsiderFetcher
from src.data.sec_edgar import SECEdgarFetcher
from src.utils.logging import get_logger

logger = get_logger(__name__)

def test_stock_act_fetcher():
    """Test STOCK Act congressional trades fetcher."""
    print("=" * 60)
    print("TESTING STOCK ACT FETCHER")
    print("=" * 60)
    
    try:
        fetcher = StockActFetcher()
        trades = fetcher.fetch_recent_trades()
        signals = fetcher.transform_to_signal_format(trades)
        
        print(f"✅ Fetched {len(trades)} congressional trades")
        print(f"✅ Transformed into {len(signals)} signals")
        
        if signals:
            sample = signals[0]
            print(f"\nSample signal:")
            print(f"  Symbol: {sample['symbol']}")
            print(f"  Direction: {sample['direction']}")
            print(f"  Filer: {sample['filer_name']}")
            print(f"  Value: ${sample['transaction_value']:,.2f}")
            print(f"  Source: {sample['source']}")
        
        return len(signals)
        
    except Exception as e:
        print(f"❌ STOCK Act fetcher failed: {e}")
        return 0

def test_openinsider_fetcher():
    """Test OpenInsider congressional trades fetcher."""
    print("\n" + "=" * 60)
    print("TESTING OPENINSIDER FETCHER")
    print("=" * 60)
    
    try:
        fetcher = OpenInsiderFetcher()
        
        # Test congressional trades
        congress_trades = fetcher.fetch_congressional_trades(limit=50)
        congress_signals = fetcher.transform_to_signal_format(congress_trades)
        
        print(f"✅ Congressional: {len(congress_trades)} trades → {len(congress_signals)} signals")
        
        # Test insider purchases
        insider_trades = fetcher.fetch_recent_buys(limit=50)
        insider_signals = fetcher.transform_to_signal_format(insider_trades)
        
        print(f"✅ Insider buys: {len(insider_trades)} trades → {len(insider_signals)} signals")
        
        total_signals = len(congress_signals) + len(insider_signals)
        
        if congress_signals:
            sample = congress_signals[0]
            print(f"\nSample congressional signal:")
            print(f"  Symbol: {sample['symbol']}")
            print(f"  Filer: {sample['filer_name']}")
            print(f"  Value: ${sample['transaction_value']:,.0f}")
            print(f"  Source: {sample['source']}")
        
        if insider_signals:
            sample = insider_signals[0]
            print(f"\nSample insider signal:")
            print(f"  Symbol: {sample['symbol']}")
            print(f"  Filer: {sample['filer_name']}")
            print(f"  Value: ${sample['transaction_value']:,.0f}")
            print(f"  Source: {sample['source']}")
        
        return total_signals
        
    except Exception as e:
        print(f"❌ OpenInsider fetcher failed: {e}")
        return 0

def test_sec_edgar_fetcher():
    """Test SEC EDGAR fetcher."""
    print("\n" + "=" * 60)
    print("TESTING SEC EDGAR FETCHER")
    print("=" * 60)
    
    try:
        fetcher = SECEdgarFetcher()
        
        # Test Form 4 fetching
        form4_filings = fetcher.fetch_recent_form4(limit=10)
        print(f"✅ Form 4: {len(form4_filings)} filings")
        
        # Test 13F fetching
        form13f_filings = fetcher.fetch_recent_13f(limit=10)
        print(f"✅ 13F: {len(form13f_filings)} filings")
        
        total_signals = len(form4_filings) + len(form13f_filings)
        
        if form4_filings:
            sample = form4_filings[0]
            print(f"\nSample Form 4:")
            print(f"  Data: {sample}")
        
        return total_signals
        
    except Exception as e:
        print(f"❌ SEC EDGAR fetcher failed: {e}")
        return 0

def analyze_database_signals():
    """Analyze signals currently in the database."""
    print("\n" + "=" * 60)
    print("DATABASE SIGNAL ANALYSIS")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # 1. Count by source
        print("\n1. Signals by source (all time):")
        by_source = db.query(
            Signal.source,
            func.count(Signal.id)
        ).group_by(Signal.source).all()
        
        total_signals = 0
        for source, count in by_source:
            print(f"   {source:20}: {count:6} signals")
            total_signals += count
        
        print(f"   {'TOTAL':20}: {total_signals:6} signals")
        
        # 2. Recent signals (past 7 days)
        print("\n2. Recent signals (past 7 days):")
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = db.query(
            Signal.source,
            func.count(Signal.id)
        ).filter(
            Signal.filing_date >= week_ago
        ).group_by(Signal.source).all()
        
        recent_total = 0
        for source, count in recent:
            print(f"   {source:20}: {count:6} signals")
            recent_total += count
        
        print(f"   {'TOTAL':20}: {recent_total:6} signals")
        
        # 3. Status breakdown
        print("\n3. Signal status:")
        by_status = db.query(
            Signal.status,
            func.count(Signal.id)
        ).group_by(Signal.status).all()
        
        for status, count in by_status:
            print(f"   {status:15}: {count:6} signals")
        
        # 4. Sample recent signals
        print("\n4. Most recent 10 signals:")
        samples = db.query(Signal).order_by(
            Signal.filing_date.desc()
        ).limit(10).all()
        
        for sig in samples:
            filing_date = sig.filing_date.strftime('%Y-%m-%d') if sig.filing_date else 'N/A'
            value = f"${sig.transaction_value:,.0f}" if sig.transaction_value else 'N/A'
            print(f"   {sig.source:15} {sig.symbol:6} {sig.filer_name[:30]:30} {filing_date} {value}")
        
        # 5. Conviction tier breakdown
        print("\n5. Conviction tier breakdown:")
        by_tier = db.query(
            Signal.conviction_tier,
            func.count(Signal.id)
        ).filter(
            Signal.status == 'ACTIVE'
        ).group_by(Signal.conviction_tier).all()
        
        for tier, count in by_tier:
            print(f"   {tier or 'NULL':15}: {count:6} signals")
        
        # 6. Top symbols by signal count
        print("\n6. Top symbols by signal count:")
        top_symbols = db.query(
            Signal.symbol,
            func.count(Signal.id)
        ).filter(
            Signal.status == 'ACTIVE'
        ).group_by(Signal.symbol).order_by(
            func.count(Signal.id).desc()
        ).limit(10).all()
        
        for symbol, count in top_symbols:
            print(f"   {symbol:10}: {count:3} signals")
        
        return {
            'total_signals': total_signals,
            'recent_signals': recent_total,
            'active_signals': db.query(Signal).filter(Signal.status == 'ACTIVE').count(),
            'sources': len(by_source)
        }
        
    finally:
        db.close()

def main():
    """Main verification function."""
    print("🔍 SIGNAL SOURCE VERIFICATION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test each fetcher
    stock_act_signals = test_stock_act_fetcher()
    openinsider_signals = test_openinsider_fetcher()
    sec_edgar_signals = test_sec_edgar_fetcher()
    
    # Analyze database
    db_stats = analyze_database_signals()
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    print(f"\n📊 FETCHER TEST RESULTS:")
    print(f"   STOCK Act:      {stock_act_signals:3} signals")
    print(f"   OpenInsider:    {openinsider_signals:3} signals")
    print(f"   SEC EDGAR:      {sec_edgar_signals:3} signals")
    print(f"   Total fetched:  {stock_act_signals + openinsider_signals + sec_edgar_signals:3} signals")
    
    print(f"\n💾 DATABASE STATISTICS:")
    print(f"   Total signals:  {db_stats['total_signals']:3}")
    print(f"   Recent (7d):    {db_stats['recent_signals']:3}")
    print(f"   Active:         {db_stats['active_signals']:3}")
    print(f"   Sources:        {db_stats['sources']:3}")
    
    # Recommendations
    print(f"\n🎯 RECOMMENDATIONS:")
    
    if db_stats['recent_signals'] < 50:
        print("   ⚠️  LOW SIGNAL VOLUME: Need more recent signals for 90-day cycles")
        print("   💡 Consider adding Form 4 insider trades (100s per day)")
        print("   💡 Consider adding 13D activist filings (high quality)")
    
    if sec_edgar_signals == 0:
        print("   ⚠️  SEC EDGAR NOT WORKING: Form 4 fetcher returns empty")
        print("   💡 Implement actual SEC EDGAR parsing")
    
    if db_stats['sources'] < 3:
        print("   ⚠️  LIMITED SOURCES: Only using congressional trades")
        print("   💡 Add insider trading and activist investor sources")
    
    if db_stats['active_signals'] < 20:
        print("   ⚠️  LOW ACTIVE SIGNALS: May not hit 50 trades/cycle target")
        print("   💡 Review signal scoring and quality filters")
    
    print(f"\n✅ TARGET METRICS:")
    print(f"   Recent signals (7d): 50+ ✅" if db_stats['recent_signals'] >= 50 else f"   Recent signals (7d): 50+ ❌ ({db_stats['recent_signals']})")
    print(f"   Active signals:      50+ ✅" if db_stats['active_signals'] >= 50 else f"   Active signals:      50+ ❌ ({db_stats['active_signals']})")
    print(f"   Signal sources:      3+  ✅" if db_stats['sources'] >= 3 else f"   Signal sources:      3+  ❌ ({db_stats['sources']})")

if __name__ == '__main__':
    main()
