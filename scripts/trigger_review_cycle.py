#!/usr/bin/env python3
"""
Manually trigger the tier escalation review cycle.
Useful for testing and immediate execution.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.base import SessionLocal
from src.core.review_cycle_manager import ReviewCycleManager

def trigger_review_cycle():
    """Manually execute a tier escalation review cycle."""
    print("🥋 Manually Triggering Tier Escalation Review Cycle")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        print("\nRunning review cycle...")
        manager = ReviewCycleManager(db)
        result = manager.execute_review_cycle()
        
        print(f"\n✓ Review cycle completed!")
        print(f"\nResults:")
        print(f"  - Review timestamp: {result.get('review_timestamp')}")
        print(f"  - Potential escalations found: {result.get('potential_escalations', 0)}")
        print(f"  - Escalations executed: {result.get('executed_escalations', 0)}")
        
        if result.get('executed_escalations', 0) > 0:
            print(f"\n  Executed escalations:")
            for i, escalation in enumerate(result.get('escalations', []), 1):
                print(f"    {i}. {escalation.get('symbol')}: {escalation.get('from_tier')} -> {escalation.get('to_tier')}")
        else:
            print(f"\n  No escalations executed (this is normal if:")
            print(f"    - No positions need escalation")
            print(f"    - Signals haven't persisted for 2 cycles yet")
            print(f"    - No tier differences detected)")
        
        print("\n" + "=" * 60)
        print("✅ Review cycle execution complete!")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error executing review cycle: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    success = trigger_review_cycle()
    sys.exit(0 if success else 1)

