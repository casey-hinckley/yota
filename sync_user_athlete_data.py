#!/usr/bin/env python3
"""
Script to sync age and gender data from Athlete records to User records.

This script matches users to athletes based on name similarity and updates
the user's age and gender fields with data from the corresponding athlete record.
"""

import sys
import os
from datetime import datetime
from difflib import SequenceMatcher

# Add the current directory to Python path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User, Athlete

def similarity(a, b):
    """Calculate similarity between two strings (0-1 scale)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def match_user_to_athlete(user):
    """
    Find the best matching athlete for a given user.
    Returns the athlete object if found, None otherwise.
    """
    user_full_name = user.get_full_name()
    
    # Strategy 1: Exact match with full name
    athlete = Athlete.query.filter_by(name=user_full_name).first()
    if athlete:
        return athlete
    
    # Strategy 2: Match using preferred name
    # Look for athletes where preferred name matches user's first name
    athlete = Athlete.query.filter(
        Athlete.preferred_name == user.first_name,
        Athlete.name.like(f'%{user.last_name}%')
    ).first()
    if athlete:
        return athlete
    
    # Strategy 3: Match using first and last name separately
    athletes = Athlete.query.all()
    best_match = None
    best_score = 0.0
    
    for athlete in athletes:
        if not athlete.name:
            continue
            
        # Check if athlete name contains both first and last name
        if (user.first_name.lower() in athlete.name.lower() and 
            user.last_name.lower() in athlete.name.lower()):
            # Calculate similarity score
            score = similarity(user_full_name, athlete.name)
            if score > best_score:
                best_match = athlete
                best_score = score
    
    # Only return if similarity is above threshold
    if best_score > 0.6:  # 60% similarity threshold
        return best_match
    
    # Strategy 4: Username match (remove spaces from athlete name)
    username_match = Athlete.query.filter(
        Athlete.name.ilike(f"%{user.username}%")
    ).first()
    if username_match:
        return username_match
    
    return None

def sync_user_athlete_data(dry_run=True):
    """
    Sync age and gender data from athletes to users.
    
    Args:
        dry_run (bool): If True, only show what would be updated without making changes
    """
    app = create_app()
    
    with app.app_context():
        print("🔍 Starting user-athlete data sync...")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        print("-" * 50)
        
        # Get all users who are not coaches (athletes)
        users = User.query.filter(User.user_type != 'coach').all()
        athletes = Athlete.query.all()
        
        print(f"Found {len(users)} users and {len(athletes)} athletes")
        print()
        
        updated_count = 0
        matched_count = 0
        no_match_count = 0
        
        for user in users:
            print(f"Processing user: {user.get_full_name()} (ID: {user.id})")
            
            # Find matching athlete
            athlete = match_user_to_athlete(user)
            
            if not athlete:
                print(f"  ❌ No matching athlete found")
                no_match_count += 1
                print()
                continue
            
            matched_count += 1
            print(f"  ✅ Matched with athlete: {athlete.name} (ID: {athlete.id})")
            
            # Check if update is needed
            needs_age_update = user.age != athlete.age
            needs_gender_update = user.gender != athlete.gender
            
            if not needs_age_update and not needs_gender_update:
                print(f"  ℹ️  Age and gender already match - no update needed")
                print()
                continue
            
            # Show what will be updated
            updates = []
            if needs_age_update:
                updates.append(f"age: {user.age} → {athlete.age}")
            if needs_gender_update:
                updates.append(f"gender: {user.gender} → {athlete.gender}")
            
            print(f"  📝 Updates needed: {', '.join(updates)}")
            
            if not dry_run:
                # Perform the update
                if needs_age_update:
                    user.age = athlete.age
                if needs_gender_update:
                    user.gender = athlete.gender
                
                db.session.commit()
                print(f"  ✅ Updated successfully")
                updated_count += 1
            else:
                print(f"  🔍 Would update (dry run mode)")
                updated_count += 1
            
            print()
        
        # Summary
        print("=" * 50)
        print("SYNC SUMMARY")
        print("=" * 50)
        print(f"Total users processed: {len(users)}")
        print(f"Users matched to athletes: {matched_count}")
        print(f"Users with no match: {no_match_count}")
        if dry_run:
            print(f"Updates that would be made: {updated_count}")
        else:
            print(f"Updates completed: {updated_count}")
        
        # Show unmatched users for manual review
        if no_match_count > 0:
            print("\n" + "=" * 50)
            print("USERS WITHOUT MATCHES (may need manual review)")
            print("=" * 50)
            for user in users:
                athlete = match_user_to_athlete(user)
                if not athlete:
                    print(f"- {user.get_full_name()} (username: {user.username})")

def main():
    """Main function with command line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync age and gender data from athletes to users')
    parser.add_argument('--live', action='store_true', 
                       help='Perform actual updates (default is dry run)')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be updated without making changes (default)')
    
    args = parser.parse_args()
    
    # If --live is specified, override dry_run
    dry_run = not args.live
    
    if dry_run:
        print("🔍 Running in DRY RUN mode - no changes will be made")
        print("Use --live flag to perform actual updates")
        print()
    
    sync_user_athlete_data(dry_run=dry_run)

if __name__ == '__main__':
    main()
