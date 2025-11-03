#!/usr/bin/env python3
"""
Full System Reset Script
Clears all trading data and initializes a fresh 30-day cycle trial.
"""

import sys
import os
sys.path.append('/app')

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from config.settings import get_settings

def reset_all_data():
    """Reset all trading data and initialize fresh trial."""
    try:
        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)
        
        print("🔄 Starting full system reset...")
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # 1. Clear all position data
                print("📊 Clearing position history...")
                conn.execute(text("DELETE FROM positions"))
                conn.execute(text("DELETE FROM scenario_positions"))
                conn.execute(text("DELETE FROM scenario_trades"))
                
                # 2. Clear order history
                print("📋 Clearing order history...")
                conn.execute(text("DELETE FROM orders"))
                
                # 3. Clear audit logs
                print("📝 Clearing audit logs...")
                conn.execute(text("DELETE FROM audit_log"))
                
                # 4. Clear cycle data
                print("🔄 Clearing cycle data...")
                conn.execute(text("DELETE FROM cycle_states"))
                conn.execute(text("DELETE FROM cycles"))
                
                # 5. Reset scenario performance data
                print("🎯 Resetting scenario performance...")
                conn.execute(text("""
                    UPDATE scenarios SET 
                        current_capital = 100000.0,
                        total_pnl = 0.0,
                        total_return_pct = 0.0,
                        total_trades = 0,
                        winning_trades = 0,
                        losing_trades = 0,
                        win_rate = 0.0,
                        max_drawdown = 0.0,
                        sharpe_ratio = 0.0,
                        last_updated = NOW()
                    WHERE is_active = true
                """))
                
                # 6. Clear philosophy state
                print("🧠 Resetting philosophy state...")
                conn.execute(text("DELETE FROM philosophy_state"))
                
                # 7. Reset signal persistence
                print("📡 Resetting signal persistence...")
                conn.execute(text("UPDATE signals SET persisted_cycles = 0"))
                
                # 8. Create fresh cycle
                print("🚀 Creating fresh 30-day cycle...")
                cycle_start = datetime.utcnow()
                cycle_end = cycle_start + timedelta(days=30)
                cycle_id = f"cycle_{cycle_start.strftime('%Y%m%d_%H%M%S')}"
                
                conn.execute(text("""
                    INSERT INTO cycles (
                        cycle_id, 
                        start_date, 
                        end_date, 
                        status, 
                        max_positions,
                        target_position_size,
                        max_position_size,
                        min_position_size,
                        total_invested,
                        total_return,
                        total_pnl,
                        positions_opened,
                        positions_closed,
                        signals_analyzed
                    ) VALUES (
                        :cycle_id,
                        :start_date,
                        :end_date,
                        'ACTIVE',
                        10,
                        0.03,
                        0.05,
                        0.01,
                        0.0,
                        0.0,
                        0.0,
                        0,
                        0,
                        0
                    )
                """), {
                    'cycle_id': cycle_id,
                    'start_date': cycle_start,
                    'end_date': cycle_end
                })
                
                # 9. Initialize fresh philosophy state
                print("⚙️ Initializing philosophy state...")
                today = datetime.utcnow().date()
                conn.execute(text("""
                    INSERT INTO philosophy_state (
                        date,
                        decisions_logged,
                        intuition_overrides,
                        trades_with_safety,
                        trades_without_safety,
                        cluster_signals_detected,
                        cluster_positions_taken,
                        positions_retired,
                        avg_return_per_cycle,
                        positions_extended,
                        avg_sharpe_at_extension,
                        rule_violations,
                        violated_rules,
                        current_allocation_power
                    ) VALUES (
                        :date,
                        0,
                        0,
                        0.0,
                        0.0,
                        0,
                        0,
                        0,
                        0.0,
                        0,
                        0.0,
                        0,
                        '{}',
                        1.0
                    )
                """), {
                    'date': today
                })
                
                # Commit all changes
                trans.commit()
                
                print("✅ Full system reset completed successfully!")
                print(f"📅 New 30-day cycle started: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"📅 Cycle ends: {cycle_end.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print("💰 All scenarios reset to $100,000 starting capital")
                print("🎯 Ready for fresh 30-day trial!")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error during reset: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False

def verify_reset():
    """Verify that the reset was successful."""
    try:
        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Check position counts
            positions = conn.execute(text("SELECT COUNT(*) FROM positions")).scalar()
            scenario_positions = conn.execute(text("SELECT COUNT(*) FROM scenario_positions")).scalar()
            orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
            
            # Check scenario capital
            scenarios = conn.execute(text("""
                SELECT scenario_name, current_capital, total_pnl 
                FROM scenarios 
                WHERE is_active = true
            """)).fetchall()
            
            # Check active cycle
            active_cycle = conn.execute(text("""
                SELECT cycle_id, start_date, end_date, status 
                FROM cycle_states 
                WHERE status = 'ACTIVE'
            """)).fetchone()
            
            print("\n🔍 Reset Verification:")
            print(f"📊 Positions: {positions} (should be 0)")
            print(f"📊 Scenario Positions: {scenario_positions} (should be 0)")
            print(f"📋 Orders: {orders} (should be 0)")
            
            print(f"\n🎯 Scenario Status:")
            for scenario in scenarios:
                print(f"  {scenario[0]}: ${scenario[1]:,.0f} capital, ${scenario[2]:,.0f} P&L")
            
            if active_cycle:
                print(f"\n🔄 Active Cycle: {active_cycle[0]}")
                print(f"   Start: {active_cycle[1]}")
                print(f"   End: {active_cycle[2]}")
                print(f"   Status: {active_cycle[3]}")
            
            return positions == 0 and scenario_positions == 0 and orders == 0
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🥋 Dojo Allocator - Full System Reset")
    print("=" * 50)
    
    # Confirm reset
    print("⚠️  This will clear ALL trading data and start fresh!")
    print("📊 All positions, orders, and performance data will be deleted.")
    print("💰 All scenarios will reset to $100,000 starting capital.")
    print("🔄 A new 30-day cycle will be created.")
    print()
    
    # Perform reset
    success = reset_all_data()
    
    if success:
        # Verify reset
        verified = verify_reset()
        
        if verified:
            print("\n🎉 Reset completed and verified successfully!")
            print("🚀 System is ready for the 30-day trial!")
            print("\nNext steps:")
            print("1. Check the dashboard for clean data")
            print("2. Monitor scenario performance as they start trading")
            print("3. Compare risk profiles over the 30-day period")
        else:
            print("\n⚠️  Reset completed but verification failed!")
            print("Please check the database manually.")
    else:
        print("\n❌ Reset failed! Please check the logs and try again.")
    
    sys.exit(0 if success else 1)
