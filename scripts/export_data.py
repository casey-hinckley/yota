import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, Athlete, Attendance, SwimTime

def export_athletes():
    """Export athletes data to CSV"""
    athletes = Athlete.query.all()
    with open('athletes.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'name', 'preferred_name', 'age', 'birthday', 'roster', 'gender']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for athlete in athletes:
            writer.writerow({
                'id': athlete.id,
                'name': athlete.name,
                'preferred_name': athlete.preferred_name,
                'age': athlete.age,
                'birthday': athlete.birthday,
                'roster': athlete.roster,
                'gender': athlete.gender
            })
    print("Exported athletes to athletes.csv")

def export_attendance():
    """Export attendance data to CSV"""
    attendances = Attendance.query.all()
    with open('attendance.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'athlete_id', 'date', 'status', 'attendance_value', 'skips', 'notes', 'created_at', 'updated_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for att in attendances:
            writer.writerow({
                'id': att.id,
                'athlete_id': att.athlete_id,
                'date': att.date,
                'status': att.status,
                'attendance_value': att.attendance_value,
                'skips': att.skips,
                'notes': att.notes,
                'created_at': att.created_at,
                'updated_at': att.updated_at
            })
    print("Exported attendance to attendance.csv")

def export_swim_times():
    """Export swim times data to CSV"""
    swim_times = SwimTime.query.all()
    with open('swim_times.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'athlete_id', 'event', 'best_time', 'time_seconds', 'course', 'meet_name', 'meet_date', 'prelim_final', 'rank', 'created_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for st in swim_times:
            writer.writerow({
                'id': st.id,
                'athlete_id': st.athlete_id,
                'event': st.event,
                'best_time': st.best_time,
                'time_seconds': st.time_seconds,
                'course': st.course,
                'meet_name': st.meet_name,
                'meet_date': st.meet_date,
                'prelim_final': st.prelim_final,
                'rank': st.rank,
                'created_at': st.created_at
            })
    print("Exported swim times to swim_times.csv")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        export_athletes()
        export_attendance()
        export_swim_times()
        print("Data export complete!")