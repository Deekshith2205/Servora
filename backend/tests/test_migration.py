from sqlalchemy import create_engine, text
from app.db.database import run_migrations
from app.db.models import Base, Ticket

def test_migration_fresh_schema():
    # Fresh schema created by Base.metadata.create_all
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    
    # Should be a no-op but safe
    run_migrations(engine)
    
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info('tickets')")).fetchall()
        has_resolved_at = any(col[1] == 'resolved_at' for col in columns)
        assert has_resolved_at, "resolved_at should be present in fresh schema"

def test_migration_existing_schema_missing_column():
    engine = create_engine("sqlite:///:memory:")
    
    with engine.begin() as conn:
        # Create tickets table manually without resolved_at
        conn.execute(text("""
            CREATE TABLE tickets (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                category VARCHAR,
                subject VARCHAR,
                message VARCHAR,
                sentiment VARCHAR,
                urgency INTEGER,
                status VARCHAR,
                confidence FLOAT,
                created_at DATETIME
            )
        """))
        # Insert a test row to ensure data is preserved
        conn.execute(text("INSERT INTO tickets (id, customer_id, category, subject, message, sentiment, urgency, status, confidence, created_at) VALUES (1, 1, 'order', 'Test', 'Test', 'neutral', 0, 'open', 0.5, '2023-01-01 00:00:00')"))
        
    # Run migration
    run_migrations(engine)
    
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info('tickets')")).fetchall()
        has_resolved_at = any(col[1] == 'resolved_at' for col in columns)
        assert has_resolved_at, "resolved_at should have been added by migration"
        
        # Verify data is preserved
        row = conn.execute(text("SELECT id, resolved_at FROM tickets WHERE id=1")).fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] is None, "New column should be null for existing rows"
        
    # Run migration again to ensure it's idempotent
    run_migrations(engine)
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info('tickets')")).fetchall()
        has_resolved_at = sum(1 for col in columns if col[1] == 'resolved_at')
        assert has_resolved_at == 1, "Should only have one resolved_at column after repeated runs"
