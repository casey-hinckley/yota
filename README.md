# Athlete Metrics Tracker

A Flask application for tracking athlete metrics throughout the season, including attendance, practice stops, effort, and attitude.

## Features

- Track multiple athletes
- Record daily metrics including:
  - Attendance
  - Number of stops during practice
  - Effort score (1-5 scale)
  - Attitude score (1-5 scale)
  - Additional notes
- View detailed history for each athlete
- Modern, responsive interface

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:5000`

## Usage

1. Add athletes using the "Add Athlete" button
2. Click on an athlete to view their metrics
3. Add new metrics for each practice session
4. Track progress over time through the detailed view

## Development

The application uses:
- Flask for the web framework
- SQLAlchemy for database management
- Bootstrap 5 for the frontend
- SQLite for data storage