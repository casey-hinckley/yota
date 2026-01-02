import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db

def add_attendance_start_date_column():
    """Add attendance_start_date column to athlete table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Add the column using raw SQL
            db.session.execute(db.text("""
                ALTER TABLE athlete 
                ADD COLUMN IF NOT EXISTS attendance_start_date DATE
            """))
            db.session.commit()
            print("✅ Successfully added attendance_start_date column to athlete table")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding column: {e}")
            # Try without IF NOT EXISTS for older PostgreSQL versions
            try:
                db.session.execute(db.text("""
                    ALTER TABLE athlete 
                    ADD COLUMN attendance_start_date DATE
                """))
                db.session.commit()
                print("✅ Successfully added attendance_start_date column to athlete table")
            except Exception as e2:
                db.session.rollback()
                print(f"❌ Error on second attempt: {e2}")
                raise

if __name__ == "__main__":
    add_attendance_start_date_column()

