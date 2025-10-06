from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, Athlete, Attendance, User, WellnessEntry
from datetime import datetime, date
from sqlalchemy import func, distinct
from utils import (
    get_events_from_data, get_courses_from_data,
    get_meets_from_standards
)

athletes_bp = Blueprint('athletes', __name__)

@athletes_bp.route('/')
def index():
    athletes = Athlete.query.all()
    return render_template('index.html', athletes=athletes)

@athletes_bp.route('/my-metrics')
@login_required
def my_metrics():
    """Route for athletes to view their own metrics"""
    # Find the athlete record for this user
    athlete = Athlete.query.filter(
        (Athlete.name == current_user.get_full_name()) |
        (Athlete.name.like(f'%{current_user.first_name}%{current_user.last_name}%'))
    ).first()
    
    if athlete:
        # Redirect to their athlete detail page
        return redirect(url_for('athletes.athlete_detail', athlete_id=athlete.id))
    else:
        # If no athlete record found, redirect to goals page
        flash('No athlete profile found. You can set your goals here.', 'info')
        return redirect(url_for('goals.goals'))

@athletes_bp.route('/athlete/<int:athlete_id>')
def athlete_detail(athlete_id):
    athlete = Athlete.query.get_or_404(athlete_id)
    
    with current_app.app_context():
        # Calculate attendance metrics
        attendance_metrics = calculate_attendance_metrics(athlete)
        
        # Get swim analysis data
        events = get_events_from_data()
        courses = get_courses_from_data()
        meets = get_meets_from_standards()
        
        # Check if athlete has a linked user account with wellness data
        linked_user = User.query.filter(
            (User.first_name + ' ' + User.last_name == athlete.name) |
            (User.username == athlete.name.lower().replace(' ', ''))
        ).first()
        
        wellness_available = False
        wellness_user_id = None
        
        if linked_user:
            # Check if they have any wellness entries
            wellness_count = WellnessEntry.query.filter_by(user_id=linked_user.id).count()
            if wellness_count > 0:
                wellness_available = True
                wellness_user_id = linked_user.id
        
        # Calculate skips metrics
        skips_metrics = calculate_skips_metrics(athlete)
        
        # Define wellness metrics (goals are now separate)
        wellness_metrics = {
            'sleep_hours': {'name': 'Sleep Hours', 'type': 'numeric', 'unit': 'hours'},
            'sleep_quality': {'name': 'Sleep Quality', 'type': 'scale', 'min': 1, 'max': 5, 'unit': ''},
            'energy_level': {'name': 'Energy Level', 'type': 'scale', 'min': 1, 'max': 10, 'unit': ''},
            'stress_level': {'name': 'Stress Level', 'type': 'scale', 'min': 1, 'max': 10, 'unit': ''},
            'practice_effort': {'name': 'Practice Effort', 'type': 'scale', 'min': 1, 'max': 10, 'unit': ''},
            'motivation': {'name': 'Motivation Level', 'type': 'scale', 'min': 1, 'max': 10, 'unit': ''},
            'hydration': {'name': 'Hydration', 'type': 'categorical', 'values': ['poor', 'fair', 'good', 'excellent']},
            'nutrition': {'name': 'Nutrition', 'type': 'categorical', 'values': ['poor', 'fair', 'good', 'excellent']},
            'soreness': {'name': 'Muscle Soreness', 'type': 'categorical', 'values': ['none', 'mild', 'moderate', 'severe', 'extreme']},
            'mobility': {'name': 'Mobility/Rehab Routine', 'type': 'boolean', 'unit': 'score'},
            'skips': {'name': 'Skips Score', 'type': 'numeric', 'unit': 'points'},
        }
    
    return render_template('athlete_detail.html', 
                         athlete=athlete, 
                         attendance_metrics=attendance_metrics,
                         skips_metrics=skips_metrics,
                         events=events,
                         courses=courses,
                         meets=meets,
                         wellness_available=wellness_available,
                         wellness_user_id=wellness_user_id,
                         wellness_metrics=wellness_metrics)

def calculate_attendance_metrics(athlete):
    """Calculate attendance percentage and daily data for an athlete"""
    
    # Get all attendance records for this athlete
    athlete_attendance = Attendance.query.filter_by(athlete_id=athlete.id).all()
    
    # Get all dates where at least one person in the same roster group was present
    roster_dates_query = db.session.query(distinct(Attendance.date)).join(Athlete).filter(
        Athlete.roster == athlete.roster,
        Attendance.attendance_value > 0.0
    ).order_by(Attendance.date)
    
    roster_practice_dates = [record[0] for record in roster_dates_query.all()]
    
    # Calculate attendance percentage
    total_practice_days = len(roster_practice_dates)
    athlete_present_days = len([record for record in athlete_attendance if record.attendance_value > 0.0])
    
    attendance_percentage = (athlete_present_days / total_practice_days * 100) if total_practice_days > 0 else 0
    
    # Create daily attendance data for the line graph with running score
    daily_attendance = []
    running_score = 0  # Start at 0, gain points for attendance, lose points for absences
    
    for practice_date in roster_practice_dates:
        # Find athlete's attendance record for this date
        athlete_record = next((record for record in athlete_attendance if record.date == practice_date), None)
        
        if athlete_record:
            attendance_value = athlete_record.attendance_value
            status = athlete_record.status
        else:
            attendance_value = 0.0
            status = 'absent'
        
        # Calculate points for this day:
        # +1 point for full attendance (1.0), +0.75 for 0.75, +0.5 for 0.5, +0.25 for 0.25
        # -1 point for absence (0.0) on practice days
        daily_points = attendance_value - 1.0 if attendance_value < 1.0 else attendance_value
        
        # Update running score
        running_score += daily_points
        
        daily_attendance.append({
            'date': practice_date.strftime('%Y-%m-%d'),
            'display_date': practice_date.strftime('%m/%d'),
            'attendance_value': attendance_value,
            'status': status,
            'daily_points': daily_points,
            'running_score': round(running_score, 1)
        })
    
    return {
        'attendance_percentage': round(attendance_percentage, 1),
        'total_practice_days': total_practice_days,
        'athlete_present_days': athlete_present_days,
        'daily_attendance': daily_attendance,
        'roster': athlete.roster or 'No Roster'
    }

def calculate_skips_metrics(athlete):
    """Calculate skips score and daily data for an athlete starting from today"""
    
    from datetime import date
    
    # Get all attendance records for this athlete
    athlete_attendance = Attendance.query.filter_by(athlete_id=athlete.id).all()
    
    # Get all dates where at least one person in the same roster group was present
    roster_dates_query = db.session.query(distinct(Attendance.date)).join(Athlete).filter(
        Athlete.roster == athlete.roster,
        Attendance.attendance_value > 0.0
    ).order_by(Attendance.date)
    
    roster_practice_dates = [record[0] for record in roster_dates_query.all()]
    
    # Filter to only include today and future dates
    today = date.today()
    future_practice_dates = [d for d in roster_practice_dates if d >= today]
    
    # Calculate skips score and daily data starting from today
    daily_skips = []
    running_skips_score = 0  # Start at 0 from today
    
    for practice_date in future_practice_dates:
        # Find athlete's attendance record for this date
        athlete_record = next((record for record in athlete_attendance if record.date == practice_date), None)
        
        if athlete_record:
            skips_count = athlete_record.skips or 0
        else:
            skips_count = 0
        
        # Calculate points for this day:
        # +3 points for 0 skips, -1 point for each skip
        daily_points = 3 if skips_count == 0 else -skips_count
        
        # Update running score
        running_skips_score += daily_points
        
        daily_skips.append({
            'date': practice_date.strftime('%Y-%m-%d'),
            'display_date': practice_date.strftime('%m/%d'),
            'skips_count': skips_count,
            'daily_points': daily_points,
            'running_score': round(running_skips_score, 1)
        })
    
    # Calculate summary statistics for future dates only
    total_skips = sum(day['skips_count'] for day in daily_skips)
    days_with_zero_skips = len([day for day in daily_skips if day['skips_count'] == 0])
    total_practice_days = len(daily_skips)
    average_skips_per_day = total_skips / total_practice_days if total_practice_days > 0 else 0
    
    return {
        'total_skips': total_skips,
        'days_with_zero_skips': days_with_zero_skips,
        'total_practice_days': total_practice_days,
        'average_skips_per_day': round(average_skips_per_day, 2),
        'current_skips_score': round(running_skips_score, 1),
        'daily_skips': daily_skips
    }

# Removed add_metric route since Metric model doesn't exist
