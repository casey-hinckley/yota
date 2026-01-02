import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, Athlete, Attendance


def parse_attendance_value(raw: str | None) -> float | None:
    if raw is None:
        return None

    value = str(raw).strip()
    if not value:
        return 0.0

    if value.lower() in {"x", "p", "present"}:
        return 1.0

    try:
        return float(value)
    except ValueError:
        return None


def determine_status(value: float) -> str:
    return "present" if value and value > 0 else "absent"


def ensure_attendance_record(athlete_id: int, practice_date: datetime.date, value: float, note: str | None):
    record = Attendance.query.filter_by(athlete_id=athlete_id, date=practice_date).first()
    status = determine_status(value)

    if record:
        record.attendance_value = value
        record.status = status
        record.skips = record.skips or 0
        if note:
            record.notes = note
    else:
        record = Attendance(
            athlete_id=athlete_id,
            date=practice_date,
            attendance_value=value,
            status=status,
            skips=0,
            notes=note,
        )
        db.session.add(record)


def import_attendance(csv_path: Path, year: int, delimiter: str, roster: str | None, dry_run: bool):
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        rows = [row for row in reader]

    if not rows:
        print("No data found in CSV.")
        return

    header = rows[0]
    date_columns = []
    for col in header[1:]:
        col_value = col.strip()
        if not col_value:
            continue
        try:
            date_columns.append(datetime.strptime(f"{col_value}/{year}", "%m/%d/%Y").date())
        except ValueError as exc:
            raise ValueError(f"Unable to parse date header '{col_value}': {exc}") from exc

    app = create_app()

    with app.app_context():
        processed = 0
        missing_athletes = set()
        for row in rows[1:]:
            if not row:
                continue

            athlete_name = row[0].strip()
            if not athlete_name:
                continue

            athlete_query = Athlete.query.filter(Athlete.name == athlete_name)
            if roster:
                athlete_query = athlete_query.filter(Athlete.roster == roster)
            athlete = athlete_query.first()

            if not athlete:
                missing_athletes.add(athlete_name)
                continue

            for idx, practice_date in enumerate(date_columns, start=1):
                # Guard against shorter rows
                cell_value = row[idx] if idx < len(row) else ""
                attendance_value = parse_attendance_value(cell_value)

                if attendance_value is None:
                    print(f"Skipping unrecognised value '{cell_value}' for {athlete_name} on {practice_date}")
                    continue

                note = None
                ensure_attendance_record(athlete.id, practice_date, attendance_value, note)
                processed += 1

        if missing_athletes:
            print("Unable to match the following athletes:")
            for name in sorted(missing_athletes):
                print(f"  - {name}")

        if dry_run:
            db.session.rollback()
            print(f"[Dry Run] Would process {processed} attendance updates.")
        else:
            db.session.commit()
            print(f"Successfully processed {processed} attendance updates.")


def main():
    parser = argparse.ArgumentParser(description="Import attendance data from CSV into the database.")
    parser.add_argument("csv_path", type=Path, help="Path to the CSV file (e.g. Sept Attendance - Sheet1.csv)")
    parser.add_argument("--year", type=int, required=True, help="Year to apply to the CSV date headers (e.g. 2025)")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter (default: ,)")
    parser.add_argument("--roster", help="Optional roster filter to disambiguate athlete names")
    parser.add_argument("--dry-run", action="store_true", help="Parse data without committing changes")

    args = parser.parse_args()

    if not args.csv_path.exists():
        print(f"CSV file '{args.csv_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    import_attendance(
        csv_path=args.csv_path,
        year=args.year,
        delimiter=args.delimiter,
        roster=args.roster,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

