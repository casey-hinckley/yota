#!/usr/bin/env python3
"""
Analyze attendance data for West AGS/Senior 2 group.
Calculate percentage of attended practices with 0 skips for each athlete and the entire group.
"""

import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, Athlete, Attendance


def analyze_zero_skips_attendance(roster_name):
    """Calculate percentage of attended practices with 0 skips for each athlete and the group."""
    app = create_app()
    
    with app.app_context():
        # Find all athletes in the specified roster
        athletes = Athlete.query.filter(Athlete.roster == roster_name).all()
        
        if not athletes:
            print(f"No athletes found for roster: {roster_name}")
            print("\nAvailable rosters:")
            rosters = db.session.query(Athlete.roster).filter(
                Athlete.roster.isnot(None),
                Athlete.roster != ''
            ).distinct().order_by(Athlete.roster).all()
            for roster in rosters:
                print(f"  - {roster[0]}")
            return
        
        print(f"\n{'='*80}")
        print(f"Analysis for: {roster_name}")
        print(f"Total athletes: {len(athletes)}")
        print(f"{'='*80}\n")
        
        # Store data for group calculation
        group_attended_practices = 0
        group_zero_skip_practices = 0
        
        athlete_results = []
        
        for athlete in athletes:
            # Get all attendance records for this athlete where they attended (attendance_value > 0)
            attendance_records = Attendance.query.filter(
                Attendance.athlete_id == athlete.id,
                Attendance.attendance_value > 0.0
            ).all()
            
            if not attendance_records:
                athlete_results.append({
                    'name': athlete.name,
                    'attended_practices': 0,
                    'zero_skip_practices': 0,
                    'percentage': 0.0
                })
                continue
            
            # Count practices with 0 skips
            attended_count = len(attendance_records)
            zero_skip_count = sum(1 for record in attendance_records if (record.skips or 0) == 0)
            percentage = (zero_skip_count / attended_count * 100) if attended_count > 0 else 0.0
            
            athlete_results.append({
                'name': athlete.name,
                'attended_practices': attended_count,
                'zero_skip_practices': zero_skip_count,
                'percentage': percentage
            })
            
            # Add to group totals
            group_attended_practices += attended_count
            group_zero_skip_practices += zero_skip_count
        
        # Sort by percentage (descending), then by name
        athlete_results.sort(key=lambda x: (-x['percentage'], x['name']))
        
        # Print individual athlete results
        print("Individual Athlete Results:")
        print("-" * 80)
        print(f"{'Athlete Name':<40} {'Attended':<12} {'0 Skips':<12} {'Percentage':<12}")
        print("-" * 80)
        
        for result in athlete_results:
            print(f"{result['name']:<40} {result['attended_practices']:<12} "
                  f"{result['zero_skip_practices']:<12} {result['percentage']:.1f}%")
        
        # Calculate and print group statistics
        group_percentage = (group_zero_skip_practices / group_attended_practices * 100) if group_attended_practices > 0 else 0.0
        
        print("\n" + "=" * 80)
        print("Group Summary:")
        print("-" * 80)
        print(f"Total attended practices: {group_attended_practices}")
        print(f"Practices with 0 skips: {group_zero_skip_practices}")
        print(f"Percentage with 0 skips: {group_percentage:.1f}%")
        print("=" * 80 + "\n")


if __name__ == '__main__':
    roster_name = "West AGS/Senior 2"
    
    if len(sys.argv) > 1:
        roster_name = sys.argv[1]
    
    analyze_zero_skips_attendance(roster_name)


