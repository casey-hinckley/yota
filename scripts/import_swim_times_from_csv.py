import argparse
import csv
import sys
import re
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, Athlete, SwimTime
from utils import parse_time, get_course_from_time
from sqlalchemy import func


def normalize_athlete_name(csv_name):
    """
    Convert CSV format "Last, First (Gender Age)" to database format "First Last"
    Example: "Baker, Annabelle (Girl 17)" -> "Annabelle Baker"
    """
    # Remove parentheses and content inside
    name_without_age = re.sub(r'\s*\([^)]*\)', '', csv_name)
    
    # Split by comma
    parts = [p.strip() for p in name_without_age.split(',')]
    
    if len(parts) == 2:
        last_name, first_name = parts
        return f"{first_name} {last_name}"
    elif len(parts) == 1:
        # No comma, assume it's already "First Last" format
        return parts[0]
    else:
        # Unexpected format, return as-is
        return name_without_age.strip()


def parse_date(date_str):
    """Parse date string in MM/DD/YYYY format"""
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), '%m/%d/%Y').date()
    except ValueError:
        return None


def ensure_swim_time_record(athlete_id, event, best_time, time_seconds, course, 
                            meet_name, meet_date, prelim_final, rank):
    """Create or update a swim time record"""
    # Check if this exact record already exists
    existing = SwimTime.query.filter_by(
        athlete_id=athlete_id,
        event=event,
        best_time=best_time,
        course=course,
        meet_date=meet_date,
        meet_name=meet_name
    ).first()
    
    if existing:
        # Update existing record
        existing.time_seconds = time_seconds
        existing.prelim_final = prelim_final
        existing.rank = rank
    else:
        # Create new record
        swim_time = SwimTime(
            athlete_id=athlete_id,
            event=event,
            best_time=best_time,
            time_seconds=time_seconds,
            course=course,
            meet_name=meet_name,
            meet_date=meet_date,
            prelim_final=prelim_final,
            rank=rank
        )
        db.session.add(swim_time)


def import_swim_times(csv_path: Path, dry_run: bool):
    """Import swim times from CSV file"""
    print(f"🚀 Starting swim times import from: {csv_path}")
    print(f"   Mode: {'DRY RUN (no changes will be saved)' if dry_run else 'LIVE (will commit to database)'}")
    print()
    
    print("📖 Reading CSV file...")
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter=',')
        rows = [row for row in reader]
    
    if not rows:
        print("❌ No data found in CSV.")
        return
    
    # Expected header: Rank,Event,Best Time,P/F/T,Date,Meet Name
    header = rows[0]
    expected_header = ['Rank', 'Event', 'Best Time', 'P/F/T', 'Date', 'Meet Name']
    
    if header != expected_header:
        print(f"⚠️  Warning: Expected header {expected_header}, got {header}")
    
    print(f"✅ CSV loaded: {len(rows)} total rows (including header)")
    print()
    
    app = create_app()
    
    with app.app_context():
        processed = 0
        skipped = 0
        missing_athletes = set()
        current_athlete_name = None
        current_athlete = None
        current_athlete_times = 0
        errors = []
        total_rows = len(rows) - 1  # Exclude header
        athletes_processed = 0
        
        print(f"📊 Processing {total_rows} rows...")
        print()
        
        start_time = time.time()
        
        for row_num, row in enumerate(rows[1:], start=2):  # Start at 2 (1-indexed + header)
            # Progress indicator every 500 rows
            if row_num % 500 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (total_rows - row_num + 1) / rate if rate > 0 else 0
                print(f"  📍 Row {row_num - 1:,}/{total_rows:,} ({((row_num-1)/total_rows*100):.1f}%) | "
                      f"Processed: {processed:,} times | "
                      f"Rate: {rate:.0f}/sec | "
                      f"ETA: {remaining:.0f}s")
            
            if not row or len(row) == 0:
                continue
            
            # Check if this is an athlete name row (first column has name, rest are empty)
            first_col = row[0].strip() if len(row) > 0 else ''
            
            # If first column is not a number and looks like a name, it's a new athlete
            # Athlete names are typically in quotes and contain parentheses with age/gender
            if first_col and not first_col.isdigit():
                # Check if this looks like an athlete name (contains parentheses or comma)
                looks_like_name = '(' in first_col or ',' in first_col
                
                if looks_like_name:
                    # Check if other columns are empty (indicating this is an athlete header)
                    other_cols_empty = all(not col.strip() for col in row[1:]) if len(row) > 1 else True
                    
                    if other_cols_empty:
                        # This is a new athlete section
                        csv_athlete_name = first_col.strip('"')  # Remove quotes if present
                        normalized_name = normalize_athlete_name(csv_athlete_name)
                        
                        # Try to find athlete in database
                        current_athlete = Athlete.query.filter_by(name=normalized_name).first()
                        
                        if not current_athlete:
                            # Try case-insensitive match
                            current_athlete = Athlete.query.filter(
                                func.lower(Athlete.name) == normalized_name.lower()
                            ).first()
                        
                        if not current_athlete:
                            missing_athletes.add(f"{csv_athlete_name} (normalized: {normalized_name})")
                            current_athlete = None
                            if len(missing_athletes) <= 5:  # Only log first few missing athletes
                                print(f"  ⚠️  Skipping athlete not in database: {normalized_name}")
                        else:
                            # Log completion of previous athlete if any
                            if current_athlete_times > 0:
                                print(f"    ✅ Completed: {current_athlete_times} times imported")
                            
                            current_athlete_name = csv_athlete_name
                            current_athlete_times = 0
                            athletes_processed += 1
                            print(f"  👤 [{athletes_processed}] Processing: {normalized_name} (ID: {current_athlete.id})")
                        
                        continue
            
            # If we don't have a current athlete, skip this row
            if not current_athlete:
                continue
            
            # Parse the time row
            if len(row) < 6:
                errors.append(f"Row {row_num}: Insufficient columns (expected 6, got {len(row)})")
                continue
            
            try:
                rank_str = row[0].strip()
                event = row[1].strip()
                best_time_str = row[2].strip()
                pft = row[3].strip() if len(row) > 3 else ''
                date_str = row[4].strip() if len(row) > 4 else ''
                meet_name = row[5].strip() if len(row) > 5 else ''
                
                # Skip if essential fields are missing
                if not event or not best_time_str:
                    continue
                
                # Parse rank
                rank = None
                if rank_str and rank_str.isdigit():
                    rank = int(rank_str)
                
                # Parse time and course
                time_seconds = parse_time(best_time_str)
                course = get_course_from_time(best_time_str)
                
                if time_seconds is None:
                    errors.append(f"Row {row_num}: Could not parse time '{best_time_str}'")
                    continue
                
                # Default to SCY (Short Course Yards) if no course indicator found
                # since all times in this CSV are short course
                if course is None:
                    course = 'SCY'
                    print(f"    ⚠️  Row {row_num}: No course indicator in '{best_time_str}', defaulting to SCY")
                
                # Parse date
                meet_date = parse_date(date_str)
                
                # Create or update swim time record
                ensure_swim_time_record(
                    athlete_id=current_athlete.id,
                    event=event,
                    best_time=best_time_str,
                    time_seconds=time_seconds,
                    course=course,
                    meet_name=meet_name,
                    meet_date=meet_date,
                    prelim_final=pft,
                    rank=rank
                )
                
                processed += 1
                current_athlete_times += 1
                
                # Log every 50 times for current athlete
                if current_athlete_times % 50 == 0:
                    print(f"    ... {current_athlete_times} times processed for {current_athlete.name}")
                
            except Exception as e:
                errors.append(f"Row {row_num}: Error processing row - {str(e)}")
                skipped += 1
                continue
        
        # Log final athlete if any times were processed
        if current_athlete_times > 0:
            print(f"    ✅ Completed: {current_athlete_times} times imported")
        
        elapsed_time = time.time() - start_time
        
        print()
        print("=" * 70)
        print("📊 IMPORT SUMMARY")
        print("=" * 70)
        print(f"  Total rows processed: {total_rows:,}")
        print(f"  Athletes found in database: {athletes_processed}")
        print(f"  Swim times imported: {processed:,}")
        print(f"  Records skipped (errors): {skipped:,}")
        print(f"  Time elapsed: {elapsed_time:.1f} seconds")
        if processed > 0:
            print(f"  Average rate: {processed/elapsed_time:.1f} times/second")
        print()
        
        if missing_athletes:
            print(f"⚠️  Unable to match {len(missing_athletes)} athletes (skipped):")
            if len(missing_athletes) <= 20:
                for name in sorted(missing_athletes):
                    print(f"  - {name}")
            else:
                for name in sorted(list(missing_athletes))[:20]:
                    print(f"  - {name}")
                print(f"  ... and {len(missing_athletes) - 20} more athletes")
            print()
        
        if errors:
            print(f"⚠️  {len(errors)} errors encountered:")
            for error in errors[:20]:  # Show first 20 errors
                print(f"  - {error}")
            if len(errors) > 20:
                print(f"  ... and {len(errors) - 20} more errors")
            print()
        
        if dry_run:
            db.session.rollback()
            print("🔍 DRY RUN COMPLETE - No changes were saved to the database")
            print(f"   Would import {processed:,} swim time records")
            if skipped > 0:
                print(f"   Would skip {skipped:,} records due to errors")
        else:
            db.session.commit()
            print("✅ IMPORT COMPLETE - Changes have been committed to the database")
            print(f"   Successfully imported {processed:,} swim time records")
            if skipped > 0:
                print(f"   Skipped {skipped:,} records due to errors")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Import swim times from CSV into the database."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the CSV file (e.g. swimTimes.csv)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse data without committing changes"
    )
    
    args = parser.parse_args()
    
    if not args.csv_path.exists():
        print(f"CSV file '{args.csv_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    import_swim_times(
        csv_path=args.csv_path,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()

