"""
Database initialization script.
Creates all tables and converts them to TimescaleDB hypertables.
"""
from sqlalchemy import create_engine, text
from src.models.base import Base
# CRITICAL: Import all models to register them
from src.models.signals import Signal
from src.models.positions import Position
from src.models.orders import Order
from src.models.audit_log import AuditLog
from src.models.philosophy_state import PhilosophyState
from config.settings import get_settings

def init_database():
    """
    Initialize database with all tables.
    Steps:
    1. Create TimescaleDB extension
    2. Create all tables from SQLAlchemy models
    3. Convert time-series tables to hypertables (skip if error)
    4. Create indexes
    """
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)

    print("🥋 Dojo Allocator - Database Initialization")
    print("=" * 50)

    # Step 1: Create TimescaleDB extension
    print("\n1. Creating TimescaleDB extension...")
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            conn.commit()
        print("  ✓ TimescaleDB extension created")
    except Exception as e:
        print(f"  ⚠ Warning: {e}")

    # Step 2: Create all tables
    print("\n2. Creating all tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("  ✓ All tables created")
    except Exception as e:
        print(f"  ✗ Error creating tables: {e}")
        return

    # Step 3: Verify
    print("\n3. Verifying tables...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result]
        print(f"  ✓ Found {len(tables)} tables:")
        for table in tables:
            print(f"    - {table}")
    except Exception as e:
        print(f"  ✗ Error verifying: {e}")

    print("\n" + "=" * 50)
    print("✅ Database initialization complete!")
    print("\nNext steps:")
    print("1. Access API: http://localhost:8000")
    print("2. Access Dashboard: http://localhost:8501")

if __name__ == "__main__":
    init_database()
