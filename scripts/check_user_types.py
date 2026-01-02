import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, User
from sqlalchemy import func

app = create_app()
with app.app_context():
    # Get distinct user types
    user_types = db.session.query(func.distinct(User.user_type)).all()
    print("Existing user_type values in database:")
    for ut in user_types:
        print(f"  - {ut[0]}")
    
    # Get a sample of users
    users = User.query.limit(5).all()
    print("\nSample users:")
    for u in users:
        print(f"  {u.username}: {u.user_type} ({u.first_name} {u.last_name})")

