from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from models import db, Athlete, Attendance, User, WellnessEntry, SwimTime
from datetime import datetime, date
from sqlalchemy import func, distinct
from utils import (
    get_events_from_data, get_courses_from_data,
    get_meets_from_standards
)

athletes_bp = Blueprint('athletes', __name__)

@athletes_bp.route('/')
@login_required
def index():
    # Get filter parameters
    roster_filter = request.args.get('roster', '')
    search_query = request.args.get('search', '')
    
    # Base query
    query = Athlete.query
    
    # Apply roster filter
    if roster_filter and roster_filter != 'all':
        query = query.filter(Athlete.roster == roster_filter)
    
    # Apply search filter
    if search_query:
        query = query.filter(Athlete.name.ilike(f'%{search_query}%'))
    
    athletes = query.all()
    
    # Get unique roster values for the filter dropdown
    rosters = db.session.query(distinct(Athlete.roster)).filter(Athlete.roster.isnot(None)).order_by(Athlete.roster).all()
    roster_list = [roster[0] for roster in rosters if roster[0]]
    
    return render_template('index.html', 
                         athletes=athletes, 
                         rosters=roster_list,
                         current_roster=roster_filter,
                         current_search=search_query)

@athletes_bp.route('/coach-analytics')
@login_required
def coach_analytics():
    """Coach analytics dashboard with team-wide metrics and group comparisons - optimized"""
    if current_user.user_type != 'coach':
        flash('Access denied. Coaches only.', 'error')
        return redirect(url_for('athletes.index'))
    
    # Get unique roster groups
    rosters = db.session.query(distinct(Athlete.roster)).filter(Athlete.roster.isnot(None)).order_by(Athlete.roster).all()
    roster_list = [roster[0] for roster in rosters if roster[0]]
    
    # Get selected groups from URL parameters
    selected_groups = request.args.getlist('groups')
    if not selected_groups:
        selected_groups = roster_list  # Show all groups by default
    
    # Use the same optimized logic as the API endpoint
    all_athletes = Athlete.query.filter(Athlete.roster.in_(selected_groups)).all()
    athlete_ids = [athlete.id for athlete in all_athletes]
    
    # Fetch all data at once (optimized queries)
    all_attendance = Attendance.query.filter(Attendance.athlete_id.in_(athlete_ids)).all()
    
    # Build user mapping efficiently - get all users at once
    all_users = User.query.all()
    user_map = {}
    for athlete in all_athletes:
        # Try exact match first
        full_name = athlete.name
        linked_user = next((user for user in all_users 
                           if f"{user.first_name} {user.last_name}" == full_name), None)
        if linked_user:
            user_map[athlete.id] = linked_user.id
    
    user_ids = list(user_map.values())
    all_wellness = WellnessEntry.query.filter(WellnessEntry.user_id.in_(user_ids)).all() if user_ids else []
    
    # Create lookup dictionaries
    attendance_by_athlete = {}
    for record in all_attendance:
        if record.athlete_id not in attendance_by_athlete:
            attendance_by_athlete[record.athlete_id] = []
        attendance_by_athlete[record.athlete_id].append(record)
    
    wellness_by_user = {}
    for entry in all_wellness:
        if entry.user_id not in wellness_by_user:
            wellness_by_user[entry.user_id] = []
        wellness_by_user[entry.user_id].append(entry)
    
    # Calculate combined metrics using optimized function
    combined_metrics = calculate_team_metrics_optimized(
        all_athletes, 
        attendance_by_athlete, 
        wellness_by_user, 
        user_map
    )
    
    # Calculate group-specific metrics
    athletes_by_group = {}
    for athlete in all_athletes:
        if athlete.roster not in athletes_by_group:
            athletes_by_group[athlete.roster] = []
        athletes_by_group[athlete.roster].append(athlete)
    
    group_metrics = {}
    for group in selected_groups:
        if group in athletes_by_group:
            group_metrics[group] = calculate_team_metrics_optimized(
                athletes_by_group[group],
                attendance_by_athlete,
                wellness_by_user,
                user_map
            )
    
    # For team metrics, get all athletes (not just selected groups)
    all_athletes_team = Athlete.query.all()
    team_metrics = {
        'total_athletes': len(all_athletes_team),
        'attendance_metrics': {'overall_percentage': 0, 'total_practice_days': 0, 'daily_averages': {}},
        'skips_metrics': {'daily_averages': {}, 'overall_average': 0},
        'wellness_metrics': {}
    }
    
    return render_template('coach_analytics.html',
                         team_metrics=team_metrics,
                         group_metrics=group_metrics,
                         combined_metrics=combined_metrics,
                         rosters=roster_list,
                         selected_groups=selected_groups)

@athletes_bp.route('/debug/attendance/<date_str>')
@login_required
def debug_attendance(date_str):
    """Debug endpoint to check attendance data for a specific date"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    try:
        debug_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    # Get all attendance records for this date
    attendance_records = Attendance.query.filter_by(date=debug_date).all()
    
    debug_data = []
    total_attendance_value = 0
    count = 0
    
    for record in attendance_records:
        athlete = Athlete.query.get(record.athlete_id)
        debug_data.append({
            'athlete_id': record.athlete_id,
            'athlete_name': athlete.name if athlete else 'Unknown',
            'roster': athlete.roster if athlete else 'Unknown',
            'date': record.date.strftime('%Y-%m-%d'),
            'status': record.status,
            'attendance_value': record.attendance_value,
            'skips': record.skips
        })
        total_attendance_value += record.attendance_value
        count += 1
    
    avg_attendance = total_attendance_value / count if count > 0 else 0
    
    return jsonify({
        'date': date_str,
        'total_records': count,
        'total_attendance_value': total_attendance_value,
        'average_attendance': avg_attendance,
        'records': debug_data
    })

@athletes_bp.route('/api/coach-analytics')
@login_required
def api_coach_analytics():
    """API endpoint for live coach analytics data - optimized version"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    # Get selected groups from URL parameters
    selected_groups = request.args.getlist('groups')
    if not selected_groups:
        # Get all groups if none selected
        rosters = db.session.query(distinct(Athlete.roster)).filter(Athlete.roster.isnot(None)).order_by(Athlete.roster).all()
        selected_groups = [roster[0] for roster in rosters if roster[0]]
    
    # Fetch all athletes once
    all_athletes = Athlete.query.filter(Athlete.roster.in_(selected_groups)).all()
    
    # Get all athlete IDs
    athlete_ids = [athlete.id for athlete in all_athletes]
    
    # Fetch all attendance records at once (single query)
    all_attendance = Attendance.query.filter(Attendance.athlete_id.in_(athlete_ids)).all()
    
    # Build user mapping efficiently - get all users at once
    all_users = User.query.all()
    user_map = {}
    for athlete in all_athletes:
        # Try exact match first
        full_name = athlete.name
        linked_user = next((user for user in all_users 
                           if f"{user.first_name} {user.last_name}" == full_name), None)
        if linked_user:
            user_map[athlete.id] = linked_user.id
    
    user_ids = list(user_map.values())
    all_wellness = WellnessEntry.query.filter(WellnessEntry.user_id.in_(user_ids)).all() if user_ids else []
    
    # Create lookup dictionaries for fast access
    attendance_by_athlete = {}
    for record in all_attendance:
        if record.athlete_id not in attendance_by_athlete:
            attendance_by_athlete[record.athlete_id] = []
        attendance_by_athlete[record.athlete_id].append(record)
    
    wellness_by_user = {}
    for entry in all_wellness:
        if entry.user_id not in wellness_by_user:
            wellness_by_user[entry.user_id] = []
        wellness_by_user[entry.user_id].append(entry)
    
    # Calculate combined metrics using pre-fetched data
    combined_metrics = calculate_team_metrics_optimized(
        all_athletes, 
        attendance_by_athlete, 
        wellness_by_user, 
        user_map
    )
    
    # Calculate group-specific metrics using pre-fetched data
    athletes_by_group = {}
    for athlete in all_athletes:
        if athlete.roster not in athletes_by_group:
            athletes_by_group[athlete.roster] = []
        athletes_by_group[athlete.roster].append(athlete)
    
    group_metrics = {}
    for group in selected_groups:
        if group in athletes_by_group:
            group_metrics[group] = calculate_team_metrics_optimized(
                athletes_by_group[group],
                attendance_by_athlete,
                wellness_by_user,
                user_map
            )
    
    return jsonify({
        'combined_metrics': combined_metrics,
        'group_metrics': group_metrics,
        'selected_groups': selected_groups
    })

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
@login_required
def athlete_detail(athlete_id):
    athlete = Athlete.query.get_or_404(athlete_id)
    
    # Get filter parameters to preserve when returning to athletes list
    roster_filter = request.args.get('roster', '')
    search_query = request.args.get('search', '')
    
    with current_app.app_context():
        # Calculate attendance metrics
        attendance_metrics = calculate_attendance_metrics(athlete)
        
        # Get swim analysis data
        events = get_events_from_data()
        courses = get_courses_from_data()
        meets = get_meets_from_standards()
        
        # Check if athlete has a linked user account with wellness data
        # Try multiple matching strategies including preferred name
        linked_user = None
        
        # Strategy 1: Exact match with full name
        linked_user = User.query.filter(
            User.first_name + ' ' + User.last_name == athlete.name
        ).first()
        
        # Strategy 2: Match using preferred name if available
        if not linked_user and athlete.preferred_name:
            preferred_full_name = f"{athlete.preferred_name} {athlete.name.split(' ')[-1] if ' ' in athlete.name else ''}"
            linked_user = User.query.filter(
                User.first_name + ' ' + User.last_name == preferred_full_name.strip()
            ).first()
        
        # Strategy 3: Username match (fallback)
        if not linked_user:
            linked_user = User.query.filter(
                User.username == athlete.name.lower().replace(' ', '')
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
                         wellness_metrics=wellness_metrics,
                         current_roster=roster_filter,
                         current_search=search_query)

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
        daily_points = attendance_value if attendance_value > 0 else -1.0
        
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
    """Calculate skips score and daily data for an athlete starting from October 6th, 2025"""
    
    # Get all attendance records for this athlete
    athlete_attendance = Attendance.query.filter_by(athlete_id=athlete.id).all()
    
    # Get all dates where at least one person in the same roster group was present
    roster_dates_query = db.session.query(distinct(Attendance.date)).join(Athlete).filter(
        Athlete.roster == athlete.roster,
        Attendance.attendance_value > 0.0
    ).order_by(Attendance.date)
    
    roster_practice_dates = [record[0] for record in roster_dates_query.all()]
    
    # Filter to only include October 6th, 2025 and forward (when skips tracking started)
    skips_start_date = date(2025, 10, 6)
    skips_practice_dates = [d for d in roster_practice_dates if d >= skips_start_date]
    
    # Calculate skips score and daily data starting from October 6th, 2025
    daily_skips = []
    running_skips_score = 0  # Start at 0 from October 6th, 2025
    
    for practice_date in skips_practice_dates:
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
    
    # Calculate summary statistics for October 6th, 2025 and forward
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

def calculate_team_metrics_optimized(athletes, attendance_by_athlete, wellness_by_user, user_map):
    """Optimized version - uses pre-fetched data instead of making new queries"""
    from collections import defaultdict
    
    if not athletes:
        return {
            'total_athletes': 0,
            'attendance_metrics': {},
            'wellness_metrics': {},
            'skips_metrics': {}
        }
    
    # Get attendance records from pre-fetched data
    attendance_records = []
    for athlete in athletes:
        if athlete.id in attendance_by_athlete:
            attendance_records.extend(attendance_by_athlete[athlete.id])
    
    # Get wellness entries from pre-fetched data
    wellness_entries = []
    for athlete in athletes:
        if athlete.id in user_map and user_map[athlete.id] in wellness_by_user:
            wellness_entries.extend(wellness_by_user[user_map[athlete.id]])
    
    # Calculate attendance metrics
    attendance_data = defaultdict(list)
    for record in attendance_records:
        attendance_data[record.date].append({
            'attendance_value': record.attendance_value,
            'skips': record.skips or 0
        })
    
    # Total number of athletes in this group (for percentage calculation)
    total_athletes = len(athletes)
    
    # Calculate averages
    avg_attendance_by_date = {}
    avg_skips_by_date = {}
    
    for practice_date, records in attendance_data.items():
        if records:
            # Only include this date if at least one person was present (attendance_value > 0)
            present_count = sum(1 for r in records if r['attendance_value'] > 0)
            if present_count > 0:
                date_str = practice_date.strftime('%Y-%m-%d')
                # Calculate percentage: (number present / total athletes in group)
                avg_attendance_by_date[date_str] = present_count / total_athletes
                avg_skips_by_date[date_str] = sum(r['skips'] for r in records) / len(records)
    
    # Calculate overall attendance percentage
    total_practice_days = len(avg_attendance_by_date)
    if total_practice_days > 0:
        overall_attendance = sum(avg_attendance_by_date.values()) / total_practice_days * 100
    else:
        overall_attendance = 0
    
    # Calculate skips metrics (starting from Oct 6, 2025)
    skips_start_date = date(2025, 10, 6)
    skips_start_str = skips_start_date.strftime('%Y-%m-%d')
    filtered_skips = {d: v for d, v in avg_skips_by_date.items() if d >= skips_start_str}
    
    # Calculate wellness averages
    wellness_metrics = {}
    if wellness_entries:
        # Group by metric type
        metrics = ['sleep_hours', 'sleep_quality', 'energy_level', 'stress_level', 
                  'practice_effort', 'motivation', 'hydration', 'nutrition', 'soreness', 'mobility']
        
        for metric in metrics:
            values = []
            for entry in wellness_entries:
                value = getattr(entry, metric, None)
                if value is not None:
                    if metric in ['hydration', 'nutrition']:
                        # Convert to numeric for averaging
                        value_map = {'poor': 1, 'fair': 2, 'good': 3, 'excellent': 4}
                        values.append(value_map.get(value, 0))
                    elif metric == 'soreness':
                        value_map = {'none': 0, 'mild': 1, 'moderate': 2, 'severe': 3, 'extreme': 4}
                        values.append(value_map.get(value, 0))
                    elif metric == 'mobility':
                        values.append(1 if value else 0)
                    else:
                        values.append(value)
            
            if values:
                wellness_metrics[metric] = {
                    'average': sum(values) / len(values),
                    'count': len(values)
                }
    
    return {
        'total_athletes': len(athletes),
        'attendance_metrics': {
            'overall_percentage': round(overall_attendance, 1),
            'total_practice_days': total_practice_days,
            'daily_averages': avg_attendance_by_date
        },
        'skips_metrics': {
            'daily_averages': filtered_skips,
            'overall_average': round(sum(filtered_skips.values()) / len(filtered_skips), 2) if filtered_skips else 0
        },
        'wellness_metrics': wellness_metrics
    }

def calculate_team_metrics(athletes):
    """Calculate aggregate metrics for a group of athletes"""
    from collections import defaultdict
    
    if not athletes:
        return {
            'total_athletes': 0,
            'attendance_metrics': {},
            'wellness_metrics': {},
            'skips_metrics': {}
        }
    
    # Get all attendance records for these athletes
    athlete_ids = [athlete.id for athlete in athletes]
    attendance_records = Attendance.query.filter(Attendance.athlete_id.in_(athlete_ids)).all()
    
    # Get all wellness entries for these athletes (through linked users)
    wellness_entries = []
    for athlete in athletes:
        # Try to find linked user
        linked_user = User.query.filter(
            User.first_name + ' ' + User.last_name == athlete.name
        ).first()
        
        if not linked_user and athlete.preferred_name:
            preferred_full_name = f"{athlete.preferred_name} {athlete.name.split(' ')[-1] if ' ' in athlete.name else ''}"
            linked_user = User.query.filter(
                User.first_name + ' ' + User.last_name == preferred_full_name.strip()
            ).first()
        
        if linked_user:
            user_wellness = WellnessEntry.query.filter_by(user_id=linked_user.id).all()
            wellness_entries.extend(user_wellness)
    
    # Calculate attendance metrics
    attendance_data = defaultdict(list)
    for record in attendance_records:
        attendance_data[record.date].append({
            'attendance_value': record.attendance_value,
            'skips': record.skips or 0
        })
    
    # Total number of athletes in this group (for percentage calculation)
    total_athletes = len(athletes)
    
    # Calculate averages
    avg_attendance_by_date = {}
    avg_skips_by_date = {}
    
    for practice_date, records in attendance_data.items():
        if records:
            # Only include this date if at least one person was present (attendance_value > 0)
            present_count = sum(1 for r in records if r['attendance_value'] > 0)
            if present_count > 0:
                date_str = practice_date.strftime('%Y-%m-%d')
                # Calculate percentage: (number present / total athletes in group)
                avg_attendance_by_date[date_str] = present_count / total_athletes
                avg_skips_by_date[date_str] = sum(r['skips'] for r in records) / len(records)
    
    # Calculate overall attendance percentage
    total_practice_days = len(avg_attendance_by_date)
    if total_practice_days > 0:
        overall_attendance = sum(avg_attendance_by_date.values()) / total_practice_days * 100
    else:
        overall_attendance = 0
    
    # Calculate skips metrics (starting from Oct 6, 2025)
    skips_start_date = date(2025, 10, 6)
    skips_start_str = skips_start_date.strftime('%Y-%m-%d')
    filtered_skips = {d: v for d, v in avg_skips_by_date.items() if d >= skips_start_str}
    
    # Calculate wellness averages
    wellness_metrics = {}
    if wellness_entries:
        # Group by metric type
        metrics = ['sleep_hours', 'sleep_quality', 'energy_level', 'stress_level', 
                  'practice_effort', 'motivation', 'hydration', 'nutrition', 'soreness', 'mobility']
        
        for metric in metrics:
            values = []
            for entry in wellness_entries:
                value = getattr(entry, metric, None)
                if value is not None:
                    if metric in ['hydration', 'nutrition']:
                        # Convert to numeric for averaging
                        value_map = {'poor': 1, 'fair': 2, 'good': 3, 'excellent': 4}
                        values.append(value_map.get(value, 0))
                    elif metric == 'soreness':
                        value_map = {'none': 0, 'mild': 1, 'moderate': 2, 'severe': 3, 'extreme': 4}
                        values.append(value_map.get(value, 0))
                    elif metric == 'mobility':
                        values.append(1 if value else 0)
                    else:
                        values.append(value)
            
            if values:
                wellness_metrics[metric] = {
                    'average': sum(values) / len(values),
                    'count': len(values)
                }
    
    return {
        'total_athletes': len(athletes),
        'attendance_metrics': {
            'overall_percentage': round(overall_attendance, 1),
            'total_practice_days': total_practice_days,
            'daily_averages': avg_attendance_by_date
        },
        'skips_metrics': {
            'daily_averages': filtered_skips,
            'overall_average': round(sum(filtered_skips.values()) / len(filtered_skips), 2) if filtered_skips else 0
        },
        'wellness_metrics': wellness_metrics
    }

@athletes_bp.route('/api/athlete/<int:athlete_id>', methods=['PUT'])
@login_required
def update_athlete(athlete_id):
    """Update athlete information - coaches only"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    athlete = Athlete.query.get_or_404(athlete_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Update fields if provided
        if 'name' in data:
            athlete.name = data['name'].strip()
        
        if 'preferred_name' in data:
            preferred = data['preferred_name'].strip() if data['preferred_name'] else None
            athlete.preferred_name = preferred
        
        if 'age' in data:
            age = data['age']
            athlete.age = int(age) if age and age != '' else None
        
        if 'gender' in data:
            gender = data['gender'].strip() if data['gender'] else None
            athlete.gender = gender
        
        if 'roster' in data:
            roster = data['roster'].strip() if data['roster'] else None
            athlete.roster = roster
        
        if 'birthday' in data:
            birthday = data['birthday']
            if birthday and birthday != '':
                try:
                    athlete.birthday = datetime.strptime(birthday, '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'error': 'Invalid birthday format. Use YYYY-MM-DD'}), 400
            else:
                athlete.birthday = None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Athlete updated successfully',
            'athlete': {
                'id': athlete.id,
                'name': athlete.name,
                'preferred_name': athlete.preferred_name,
                'age': athlete.age,
                'gender': athlete.gender,
                'roster': athlete.roster,
                'birthday': athlete.birthday.strftime('%Y-%m-%d') if athlete.birthday else None
            }
        })
        
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': f'Invalid data: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@athletes_bp.route('/api/athlete/<int:athlete_id>', methods=['DELETE'])
@login_required
def delete_athlete(athlete_id):
    """Delete an athlete - coaches only"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    athlete = Athlete.query.get_or_404(athlete_id)
    
    try:
        # Get counts of related data for confirmation
        attendance_count = Attendance.query.filter_by(athlete_id=athlete_id).count()
        swim_times_count = SwimTime.query.filter_by(athlete_id=athlete_id).count()
        
        # Delete all related records first
        # Delete attendance records
        Attendance.query.filter_by(athlete_id=athlete_id).delete()
        
        # Delete swim time records
        SwimTime.query.filter_by(athlete_id=athlete_id).delete()
        
        # Delete the athlete
        db.session.delete(athlete)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Athlete {athlete.name} deleted successfully',
            'deleted_data': {
                'attendance_records': attendance_count,
                'swim_times': swim_times_count
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

# Removed add_metric route since Metric model doesn't exist
