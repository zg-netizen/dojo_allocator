#!/usr/bin/env python3
"""
Create scenario tables for parallel trading execution.
"""

import sys
import os
sys.path.append('/app')

from sqlalchemy import create_engine, text
from src.models.scenarios import Scenario, ScenarioPosition, ScenarioTrade
from src.models.base import Base
from config.settings import get_settings

def create_scenario_tables():
    """Create scenario-related tables in the database."""
    try:
        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)
        
        # Create all tables
        Base.metadata.create_all(engine, tables=[
            Scenario.__table__,
            ScenarioPosition.__table__,
            ScenarioTrade.__table__
        ])
        
        print("✅ Scenario tables created successfully!")
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('scenarios', 'scenario_positions', 'scenario_trades')
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result.fetchall()]
            print(f"📊 Created tables: {', '.join(tables)}")
            
            if len(tables) == 3:
                print("🎯 All scenario tables created successfully!")
                return True
            else:
                print("❌ Some tables may not have been created properly")
                return False
                
    except Exception as e:
        print(f"❌ Error creating scenario tables: {e}")
        return False

if __name__ == "__main__":
    success = create_scenario_tables()
    sys.exit(0 if success else 1)
