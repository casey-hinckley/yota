#!/usr/bin/env python3
"""
Script to sync athlete data from Excel file (customexport.xlsx) to the database.

This script:
1. Updates age and gender from the Excel file
2. Stores preferred names (for attendance matching) while keeping actual names (for swim times)
3. Handles name matching between Excel and database

IMPORTANT: This keeps the original name intact for swim time data while adding
preferred_name for attendance matching.
"""

import sys
import os
from datetime import datetime
from difflib import SequenceMatcher
import pandas as pd

# Add the current directory to Python path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Athlete

def similarity(a, b):
    """Calculate similarity between two strings (0-1 scale)"""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def normalize_name(name):
    """Normalize a name for comparison"""
    if pd.isna(name):
        return ""
    return str(name).strip().lower()

def match_athlete_from_excel(excel_row, all_athletes):
    """
    Find the best matching athlete in the database for an Excel row.
    
    Args:
        excel_row: A row from the Excel DataFrame with columns:
                   'Memb. First Name', 'Memb. Last Name', 'Preferred Name'
        all_athletes: List of Athlete objects from database
    
    Returns:
        Athlete object if found, None otherwise
    """
    first_name = normalize_name(excel_row['Memb. First Name'])
    last_name = normalize_name(excel_row['Memb. Last Name'])
    preferred_name = normalize_name(excel_row['Preferred Name'])
    
    if not first_name or not last_name:
        return None
    
    full_name_actual = f"{excel_row['Memb. First Name']} {excel_row['Memb. Last Name']}".strip()
    
    # Strategy 1: Exact match with "First Last" format
    for athlete in all_athletes:
        if normalize_name(athlete.name) == normalize_name(full_name_actual):
            return athlete
    
    # Strategy 2: Match using first and last name components
    best_match = None
    best_score = 0.0
    
    for athlete in all_athletes:
        if not athlete.name:
            continue
        
        athlete_name_lower = normalize_name(athlete.name)
        
        # Check if both first and last names are in athlete name
        if first_name in athlete_name_lower and last_name in athlete_name_lower:
            score = similarity(full_name_actual, athlete.name)
            if score > best_score:
                best_match = athlete
                best_score = score
    
    if best_score > 0.7:  # 70% similarity threshold
        return best_match
    
    # Strategy 3: Try with preferred name if it exists
    if preferred_name:
        full_name_preferred = f"{excel_row['Preferred Name']} {excel_row['Memb. Last Name']}".strip()
        for athlete in all_athletes:
            if normalize_name(athlete.name) == normalize_name(full_name_preferred):
                return athlete
        
        # Check similarity with preferred name
        for athlete in all_athletes:
            if not athlete.name:
                continue
            
            athlete_name_lower = normalize_name(athlete.name)
            
            if preferred_name in athlete_name_lower and last_name in athlete_name_lower:
                score = similarity(full_name_preferred, athlete.name)
                if score > best_score:
                    best_match = athlete
                    best_score = score
        
        if best_score > 0.7:
            return best_match
    
    return None

def sync_athlete_data_from_excel(excel_file='customexport.xlsx', dry_run=True):
    """
    Sync athlete data from Excel file to database.
    
    Args:
        excel_file (str): Path to Excel file
        dry_run (bool): If True, only show what would be updated without making changes
    """
    app = create_app()
    
    with app.app_context():
        print("🔍 Starting athlete data sync from Excel...")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        print(f"File: {excel_file}")
        print("-" * 70)
        
        # Read Excel file
        try:
            df = pd.read_excel(excel_file)
            print(f"✅ Loaded {len(df)} rows from Excel file")
        except Exception as e:
            print(f"❌ Error reading Excel file: {e}")
            return
        
        # Get all athletes from database
        all_athletes = Athlete.query.all()
        print(f"✅ Found {len(all_athletes)} athletes in database")
        print()
        
        matched_count = 0
        updated_count = 0
        no_match_count = 0
        unmatched_excel_rows = []
        
        for idx, row in df.iterrows():
            first_name = row['Memb. First Name']
            last_name = row['Memb. Last Name']
            preferred_name = row['Preferred Name'] if pd.notna(row['Preferred Name']) else None
            age = int(row['Age']) if pd.notna(row['Age']) else None
            gender = 'Male' if row['Gender'] == 'M' else 'Female' if row['Gender'] == 'F' else None
            
            excel_name = f"{first_name} {last_name}".strip()
            print(f"Processing Excel row: {excel_name}")
            
            # Find matching athlete
            athlete = match_athlete_from_excel(row, all_athletes)
            
            if not athlete:
                print(f"  ❌ No matching athlete found in database")
                no_match_count += 1
                unmatched_excel_rows.append(excel_name)
                print()
                continue
            
            matched_count += 1
            print(f"  ✅ Matched with database athlete: {athlete.name} (ID: {athlete.id})")
            
            # Check what needs to be updated
            updates = []
            needs_update = False
            
            # Check age
            if athlete.age != age:
                updates.append(f"age: {athlete.age} → {age}")
                needs_update = True
            
            # Check gender
            if athlete.gender != gender:
                updates.append(f"gender: {athlete.gender} → {gender}")
                needs_update = True
            
            # Check preferred name - only set if it exists and is different from first name
            if preferred_name and preferred_name != first_name:
                if athlete.preferred_name != preferred_name:
                    updates.append(f"preferred_name: {athlete.preferred_name} → {preferred_name}")
                    needs_update = True
            else:
                # Clear preferred name if it doesn't exist or is same as first name
                if athlete.preferred_name is not None:
                    updates.append(f"preferred_name: {athlete.preferred_name} → None (clearing)")
                    needs_update = True
            
            if not needs_update:
                print(f"  ℹ️  All data already matches - no update needed")
                print()
                continue
            
            # Show what will be updated
            print(f"  📝 Updates needed:")
            for update in updates:
                print(f"      - {update}")
            
            if not dry_run:
                # Perform the update
                if athlete.age != age:
                    athlete.age = age
                if athlete.gender != gender:
                    athlete.gender = gender
                
                # Update preferred name logic
                if preferred_name and preferred_name != first_name:
                    athlete.preferred_name = preferred_name
                else:
                    athlete.preferred_name = None
                
                db.session.commit()
                print(f"  ✅ Updated successfully")
                updated_count += 1
            else:
                print(f"  🔍 Would update (dry run mode)")
                updated_count += 1
            
            print()
        
        # Summary
        print("=" * 70)
        print("SYNC SUMMARY")
        print("=" * 70)
        print(f"Total Excel rows processed: {len(df)}")
        print(f"Excel rows matched to database athletes: {matched_count}")
        print(f"Excel rows with no match: {no_match_count}")
        if dry_run:
            print(f"Updates that would be made: {updated_count}")
        else:
            print(f"Updates completed: {updated_count}")
        
        # Show unmatched Excel rows
        if unmatched_excel_rows:
            print("\n" + "=" * 70)
            print("EXCEL ROWS WITHOUT DATABASE MATCHES")
            print("=" * 70)
            print("These people are in the Excel file but not in the database:")
            for name in unmatched_excel_rows:
                print(f"  - {name}")
            print()
            print("💡 These might be new athletes that need to be added to the database.")
        
        # Show athletes in database but not in Excel
        matched_athlete_ids = set()
        for idx, row in df.iterrows():
            athlete = match_athlete_from_excel(row, all_athletes)
            if athlete:
                matched_athlete_ids.add(athlete.id)
        
        unmatched_db_athletes = [a for a in all_athletes if a.id not in matched_athlete_ids]
        
        if unmatched_db_athletes:
            print("\n" + "=" * 70)
            print("DATABASE ATHLETES WITHOUT EXCEL MATCHES")
            print("=" * 70)
            print(f"Found {len(unmatched_db_athletes)} athletes in database not in Excel file:")
            for athlete in unmatched_db_athletes[:20]:  # Show first 20
                print(f"  - {athlete.name} (ID: {athlete.id})")
            if len(unmatched_db_athletes) > 20:
                print(f"  ... and {len(unmatched_db_athletes) - 20} more")
            print()
            print("💡 These might be old/inactive athletes or the names don't match.")

def main():
    """Main function with command line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync athlete data from Excel file')
    parser.add_argument('--live', action='store_true', 
                       help='Perform actual updates (default is dry run)')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be updated without making changes (default)')
    parser.add_argument('--file', type=str, default='customexport.xlsx',
                       help='Path to Excel file (default: customexport.xlsx)')
    
    args = parser.parse_args()
    
    # If --live is specified, override dry_run
    dry_run = not args.live
    
    if dry_run:
        print("🔍 Running in DRY RUN mode - no changes will be made")
        print("Use --live flag to perform actual updates")
        print()
    
    sync_athlete_data_from_excel(excel_file=args.file, dry_run=dry_run)

if __name__ == '__main__':
    main()

