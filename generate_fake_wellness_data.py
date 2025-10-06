"""
Script to generate fake wellness data for testing the wellness dashboard
"""
from app import app
from models import db, WellnessEntry, User
from datetime import date, timedelta
import random

def generate_wellness_data(user_id, num_days=30):
    """
    Generate fake wellness data for the past N days for a specific user
    
    Args:
        user_id: The user ID to create wellness entries for
        num_days: Number of days of data to generate (default: 30)
    """
    with app.app_context():
        # Check if user exists
        user = User.query.get(user_id)
        if not user:
            print(f"❌ User with ID {user_id} not found")
            return
        
        print(f"Generating {num_days} days of wellness data for {user.get_full_name()}...")
        print("-" * 70)
        
        # Clear existing wellness entries for this user (optional - comment out if you want to keep existing data)
        # WellnessEntry.query.filter_by(user_id=user_id).delete()
        
        created_count = 0
        skipped_count = 0
        
        # Generate data for the past N days
        for i in range(num_days - 1, -1, -1):
            entry_date = date.today() - timedelta(days=i)
            
            # Check if entry already exists
            existing = WellnessEntry.query.filter_by(
                user_id=user_id,
                date=entry_date
            ).first()
            
            if existing:
                print(f"Skipping {entry_date} - entry already exists")
                skipped_count += 1
                continue
            
            # Generate realistic-ish data with some trends
            # Sleep tends to be better on weekends
            is_weekend = entry_date.weekday() >= 5
            
            # Sleep hours: 5-10 hours, better on weekends
            sleep_hours = random.randint(7 if is_weekend else 6, 10 if is_weekend else 8)
            
            # Sleep quality: 1-5, correlated with hours
            sleep_quality = min(5, max(1, sleep_hours - 3 + random.randint(-1, 1)))
            
            # Energy level: 1-10, correlated with sleep
            base_energy = sleep_quality * 2
            energy_level = min(10, max(1, base_energy + random.randint(-2, 2)))
            
            # Stress level: 1-10, higher during weekdays
            stress_level = random.randint(3 if is_weekend else 5, 6 if is_weekend else 9)
            
            # Practice effort: 1-10, skip some days (no practice)
            # About 20% chance of no practice
            if random.random() < 0.2:
                practice_effort = None
            else:
                practice_effort = random.randint(6, 10)
            
            # Motivation: 1-10, correlated with energy and inversely with stress
            motivation = min(10, max(1, energy_level - (stress_level // 2) + random.randint(-1, 2)))
            
            # Hydration: poor, fair, good, excellent
            hydration_options = ['poor', 'fair', 'good', 'excellent']
            hydration_weights = [5, 15, 50, 30]  # More likely to be good
            hydration = random.choices(hydration_options, weights=hydration_weights)[0]
            
            # Nutrition: poor, fair, good, excellent
            nutrition = random.choices(hydration_options, weights=hydration_weights)[0]
            
            # Soreness: none, mild, moderate, severe, extreme
            soreness_options = ['none', 'mild', 'moderate', 'severe', 'extreme']
            soreness_weights = [30, 40, 20, 8, 2]  # Most days mild or none
            soreness = random.choices(soreness_options, weights=soreness_weights)[0]
            
            # Goals: achieved or not (60% chance of achieving each goal)
            goal1_achieved = random.random() < 0.6
            goal2_achieved = random.random() < 0.6
            
            # Create the wellness entry
            entry = WellnessEntry(
                user_id=user_id,
                date=entry_date,
                sleep_hours=sleep_hours,
                sleep_quality=sleep_quality,
                energy_level=energy_level,
                stress_level=stress_level,
                practice_effort=practice_effort,
                motivation=motivation,
                hydration=hydration,
                nutrition=nutrition,
                soreness=soreness,
                goal1_achieved=goal1_achieved,
                goal2_achieved=goal2_achieved,
                additional_notes=None
            )
            
            db.session.add(entry)
            print(f"✅ Created entry for {entry_date}: Sleep={sleep_hours}hrs, Energy={energy_level}, Stress={stress_level}")
            created_count += 1
        
        # Commit all entries
        db.session.commit()
        
        print("-" * 70)
        print(f"\n✅ Successfully created {created_count} wellness entries")
        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} existing entries")
        print(f"\nYou can now view the wellness dashboard for {user.get_full_name()}!")

def list_users():
    """List all users to help identify which user to generate data for"""
    with app.app_context():
        users = User.query.all()
        print("\nAvailable Users:")
        print("-" * 70)
        for user in users:
            print(f"ID: {user.id:3d} | Username: {user.username:20s} | Name: {user.get_full_name():30s} | Type: {user.user_type}")
        print("-" * 70)

if __name__ == '__main__':
    print("=" * 70)
    print("WELLNESS DATA GENERATOR")
    print("=" * 70)
    
    # List available users
    list_users()
    
    # You can modify this to generate data for a specific user
    # Example: generate_wellness_data(user_id=1, num_days=30)
    
    print("\n📝 To generate data, edit this script and uncomment the line below,")
    print("   replacing USER_ID with the actual user ID from the list above.")
    print("\nExample:")
    print("  generate_wellness_data(user_id=1, num_days=30)")
    print("\nOr run from command line:")
    print("  python -c \"from generate_fake_wellness_data import generate_wellness_data; generate_wellness_data(1, 30)\"")
    
    # Uncomment and modify this line to generate data:
    # generate_wellness_data(user_id=1, num_days=30)

