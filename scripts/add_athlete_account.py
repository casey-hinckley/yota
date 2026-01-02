import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, User, Athlete


def add_athlete_account(first_name, last_name, username, password, age, gender, user_type='swimmer'):
    """Add an athlete account (both User and Athlete records)"""
    app = create_app()
    
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"⚠️  User with username '{username}' already exists (ID: {existing_user.id})")
            return existing_user
        
        # Check if athlete already exists
        athlete_name = f"{first_name} {last_name}"
        existing_athlete = Athlete.query.filter_by(name=athlete_name).first()
        if existing_athlete:
            print(f"⚠️  Athlete '{athlete_name}' already exists (ID: {existing_athlete.id})")
            # Still create user if it doesn't exist
            if not existing_user:
                user = User(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    password_hash=password,  # Stored as plain text
                    user_type=user_type,
                    age=age,
                    gender=gender,
                    is_active=True
                )
                db.session.add(user)
                db.session.commit()
                print(f"✅ Created user account for {athlete_name}")
                return user
            return existing_user
        
        # Create User
        # Database allows 'swimmer' or 'coach' - use 'swimmer' for athletes
        user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            password_hash=password,  # Stored as plain text
            user_type=user_type,  # 'swimmer' for athletes
            age=age,
            gender=gender,
            is_active=True
        )
        db.session.add(user)
        db.session.flush()  # Get the user ID
        
        # Create Athlete
        athlete = Athlete(
            name=athlete_name,
            age=age,
            gender=gender
        )
        db.session.add(athlete)
        db.session.commit()
        
        print(f"✅ Created user account: {username} (ID: {user.id})")
        print(f"✅ Created athlete record: {athlete_name} (ID: {athlete.id})")
        
        return user


if __name__ == "__main__":
    # Add Eleanor Johnson
    add_athlete_account(
        first_name="Eleanor",
        last_name="Johnson",
        username="eleanor.johnson",
        password="yotaswim2025",
        age=14,
        gender="Female",
        user_type="swimmer"
    )

