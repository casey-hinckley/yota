# Yota — Swim Team Metrics

A Flask web application for managing a competitive swim team. Coaches track attendance, skips, and roster data; athletes log daily wellness check-ins and personal goals; everyone can view swim time analysis and rankings.

---

## Features

**Coaches**
- Roster management — add, edit, and remove athletes
- Attendance tracking with support for partial and double-practice days
- Skips tracking (since Oct 6, 2025) with a running score system
- Coach analytics dashboard with team-wide and group-level metrics
- Debug endpoint for inspecting raw attendance data by date

**Athletes**
- Daily wellness questionnaire (sleep, energy, stress, effort, hydration, nutrition, soreness, mobility)
- Personal goal setting (2 active goals at a time, history preserved)
- Wellness dashboard with trend charts for each metric

**Both**
- Swim time analysis — view personal bests, progression charts, and qualifying cut status against `all_meet_standards.csv`
- Rankings — top skip scores, skip streaks, and goal achievement streaks across the roster

---

## Tech Stack

| Layer | Library |
|---|---|
| Web framework | Flask 3 |
| ORM | Flask-SQLAlchemy |
| Auth | Flask-Login |
| Database | Supabase (PostgreSQL) in production, SQLite locally |
| Data analysis | pandas |
| Frontend | Bootstrap 5 (Jinja2 templates) |

---

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here

# Supabase (leave blank to use SQLite locally)
SUPABASE_DB_HOST=your-supabase-host
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your-password
SUPABASE_DB_PORT=5432

# Optional
FLASK_ENV=development   # Set to 'production' to disable debug mode
PORT=5001
```

If `SUPABASE_DB_HOST` and `SUPABASE_DB_PASSWORD` are not set, the app falls back to a local SQLite file (`athlete_metrics.db`).

### 4. Run the app

```bash
python app.py
```

Navigate to `http://localhost:5001`.

For production with gunicorn:

```bash
gunicorn app:app
```

---

## User Roles

| Role | Access |
|---|---|
| `coach` | Full access — roster, attendance, analytics, all athlete data |
| athlete (any other `user_type`) | Redirected to their own athlete detail page and wellness tools |

On login, athletes are matched to an `Athlete` record using a three-strategy name lookup (exact → preferred name → partial). If no match is found, they land on the goals page.

---

## Data Files

| File | Purpose |
|---|---|
| `all_meet_standards.csv` | Qualifying cut times by meet, event, course, gender, and age group — required for swim analysis |

> The CSV files `athletes.csv`, `attendance.csv`, and `swim_times.csv` are generated outputs from `scripts/export_data.py` and should not be committed to the repo.

---

## Scripts

All scripts are run from the project root with the virtual environment active.

### Import attendance from CSV

```bash
python scripts/import_attendance_from_csv.py <csv_path> --year <YYYY> [--roster <name>] [--dry-run]
```

- CSV format: first column is athlete name, remaining columns are `MM/DD` date headers
- `--year` is required because date headers contain no year
- `--roster` narrows the athlete lookup to avoid name collisions across groups
- `--dry-run` validates and reports without writing to the database

### Import swim times from CSV

```bash
python scripts/import_swim_times_from_csv.py <csv_path> [--dry-run]
```

- CSV format: athlete name appears as a section header row (first col non-empty, rest blank), followed by their time rows (`Rank, Event, Best Time, P/F/T, Date, Meet Name`)
- Upserts records — re-running is safe
- `--dry-run` validates without committing

### Export data to CSV

```bash
python scripts/export_data.py
```

Exports all athletes, attendance, and swim times to `athletes.csv`, `attendance.csv`, and `swim_times.csv` in the working directory.

### Analyze zero-skips attendance

```bash
python scripts/analyze_zero_skips_attendance.py [roster_name]
```

Prints a table showing each athlete's percentage of attended practices with zero skips. Defaults to `"West AGS/Senior 2"`.

---

## Scoring Systems

**Attendance running score** — tracks practice attendance over time:
- Attended (partial or full): `+attendance_value`
- Missed single practice: `−1`
- Missed double-practice day: `−2`

**Skips running score** — tracks in-practice behavior (from Oct 6, 2025):
- Full attendance, 0 skips: `+3`
- Full attendance, N skips: `−N`
- Partial attendance, N skips: `−N` (no bonus)
- Absent: `0`

**Goal/mobility running score** — tracks daily achievement:
- Achieved/completed: `+1`
- Not achieved: `−1`

---

## Known Issues

- Passwords are stored as plain text. A hashed auth system has not been implemented yet.
- `User.last_login` is set on login but the column does not exist in the database schema — the assignment has no effect.
- The attendance-improvement correlation feature in swim analysis (`calculate_time_improvement_analysis`) relies on legacy CSV files that are no longer maintained.
