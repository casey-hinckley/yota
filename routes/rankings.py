from flask import Blueprint, render_template, current_app, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Athlete, Attendance, WellnessEntry
from datetime import date, timedelta
from sqlalchemy import distinct

rankings_bp = Blueprint('rankings', __name__)

def get_top_with_ties(items, key, top_n=5):
    """Get top N items, including all entries tied with the Nth position"""
    if not items:
        return []
    
    # Sort items by the key in descending order
    sorted_items = sorted(items, key=lambda x: x[key], reverse=True)
    
    # If we have fewer items than top_n, return all
    if len(sorted_items) <= top_n:
        return sorted_items
    
    # Get the value at the Nth position
    cutoff_value = sorted_items[top_n - 1][key]
    
    # Include all items with value >= cutoff_value
    result = [item for item in sorted_items if item[key] >= cutoff_value]
    
    return result

@rankings_bp.route('/api/rankings')
@login_required
def api_rankings():
    """API endpoint for rankings data - returns JSON"""
    
    # Get filter parameters
    selected_groups = request.args.getlist('groups')
    time_range = request.args.get('time_range', 'all')  # all, week, month
    
    with current_app.app_context():
        # Get unique roster groups for filter
        rosters = db.session.query(distinct(Athlete.roster)).filter(Athlete.roster.isnot(None)).order_by(Athlete.roster).all()
        roster_list = [roster[0] for roster in rosters if roster[0]]
        
        # If no groups selected, show all groups
        if not selected_groups:
            selected_groups = roster_list
        
        # Calculate date range based on filter
        today = date.today()
        if time_range == 'week':
            # Current week: Monday to Saturday
            # weekday() returns 0=Monday, 1=Tuesday, ... 6=Sunday
            days_since_monday = today.weekday()
            start_date = today - timedelta(days=days_since_monday)  # This Monday
            
            # If today is Sunday (6), we want to show last week (previous Monday-Saturday)
            if today.weekday() == 6:
                start_date = start_date - timedelta(days=7)  # Go back to previous Monday
            
            # End date is Saturday of current week
            days_until_saturday = 5 - today.weekday()  # 5 = Saturday
            if days_until_saturday < 0:  # If today is Sunday
                end_date = today - timedelta(days=1)  # Yesterday (Saturday)
            else:
                end_date = today + timedelta(days=days_until_saturday)
            
            # Don't go beyond today
            if end_date > today:
                end_date = today
        
        elif time_range == 'lastweek':
            # Last week: Previous Monday to Saturday
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            
            # Go back one week
            start_date = this_monday - timedelta(days=7)  # Last Monday
            end_date = start_date + timedelta(days=5)  # Last Saturday
                
        elif time_range == 'month':
            # Current month: 1st of the month to today
            start_date = date(today.year, today.month, 1)
            end_date = today
        else:  # 'all'
            start_date = date(2020, 1, 1)  # Far enough back to include all data
            end_date = today
        
        # Fetch all data at once (optimized queries), filtered by selected groups
        all_athletes = Athlete.query.filter(Athlete.roster.in_(selected_groups)).all() if selected_groups else []
        
        # Filter attendance by date range
        all_attendance = Attendance.query.filter(
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
        
        # Get athlete IDs for user mapping
        athlete_ids = [athlete.id for athlete in all_athletes]
        
        # Get all users and filter wellness by date range
        all_users = User.query.filter(User.user_type != 'coach').all()
        all_wellness = WellnessEntry.query.filter(
            WellnessEntry.date >= start_date,
            WellnessEntry.date <= end_date
        ).all()
        
        # Create lookup dictionaries for O(1) access
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
        
        # Get roster practice dates once per roster (not per athlete)
        roster_dates_cache = {}
        for athlete in all_athletes:
            if athlete.roster and athlete.roster not in roster_dates_cache:
                roster_dates_query = db.session.query(distinct(Attendance.date)).join(Athlete).filter(
                    Athlete.roster == athlete.roster,
                    Attendance.attendance_value > 0.0
                ).order_by(Attendance.date)
                roster_dates_cache[athlete.roster] = [record[0] for record in roster_dates_query.all()]
        
        # Calculate rankings using pre-fetched data, respecting date range
        skip_scores = calculate_all_skip_scores_optimized(all_athletes, attendance_by_athlete, roster_dates_cache, start_date, end_date)
        skip_streaks = calculate_all_skip_streaks_optimized(all_athletes, attendance_by_athlete, roster_dates_cache, start_date, end_date)
        goal_streaks = calculate_all_goal_streaks_optimized(all_users, wellness_by_user, start_date, end_date, selected_groups, all_athletes)
        
        # Get top 5 for each category, including all tied entries
        top_skip_scores = get_top_with_ties(skip_scores, 'score', 5)
        top_skip_streaks = get_top_with_ties(skip_streaks, 'streak', 5)
        top_goal_streaks = get_top_with_ties(goal_streaks, 'streak', 5)
        
        return jsonify({
            'top_skip_scores': top_skip_scores,
            'top_skip_streaks': top_skip_streaks,
            'top_goal_streaks': top_goal_streaks
        })

@rankings_bp.route('/rankings')
@login_required
def rankings():
    """Rankings page - loads initial view"""
    
    with current_app.app_context():
        # Get unique roster groups for filter
        rosters = db.session.query(distinct(Athlete.roster)).filter(Athlete.roster.isnot(None)).order_by(Athlete.roster).all()
        roster_list = [roster[0] for roster in rosters if roster[0]]
        
        return render_template('rankings.html',
                             rosters=roster_list)

def calculate_all_skip_scores_optimized(athletes, attendance_by_athlete, roster_dates_cache, start_date, end_date):
    """Calculate skip scores for all athletes using pre-fetched data"""
    skip_scores = []
    skips_start_date = max(date(2025, 10, 6), start_date)  # Respect both tracking start and filter start
    
    for athlete in athletes:
        if not athlete.roster or athlete.roster not in roster_dates_cache:
            continue
        
        # Get attendance records from lookup dictionary
        athlete_attendance = attendance_by_athlete.get(athlete.id, [])
        
        # Create dict for fast date lookup
        attendance_by_date = {record.date: record for record in athlete_attendance}
        
        # Get practice dates for this roster
        roster_practice_dates = roster_dates_cache[athlete.roster]
        
        # Filter to include skips start date and respect time range
        skips_practice_dates = [d for d in roster_practice_dates if d >= skips_start_date and d <= end_date]
        
        if not skips_practice_dates:
            continue
        
        # Calculate running skips score
        running_skips_score = 0
        
        for practice_date in skips_practice_dates:
            athlete_record = attendance_by_date.get(practice_date)
            
            if athlete_record:
                skips_count = athlete_record.skips or 0
            else:
                skips_count = 0
            
            # +3 points for 0 skips, -1 point for each skip
            daily_points = 3 if skips_count == 0 else -skips_count
            running_skips_score += daily_points
        
        skip_scores.append({
            'athlete_id': athlete.id,
            'athlete_name': athlete.name,
            'roster': athlete.roster,
            'score': round(running_skips_score, 1),
            'days_tracked': len(skips_practice_dates)
        })
    
    return skip_scores

def calculate_all_skip_streaks_optimized(athletes, attendance_by_athlete, roster_dates_cache, start_date, end_date):
    """Calculate current skip streaks using pre-fetched data"""
    skip_streaks = []
    skips_start_date = max(date(2025, 10, 6), start_date)  # Respect both tracking start and filter start
    
    for athlete in athletes:
        if not athlete.roster or athlete.roster not in roster_dates_cache:
            continue
        
        # Get attendance records from lookup dictionary
        athlete_attendance = attendance_by_athlete.get(athlete.id, [])
        
        # Create dict for fast date lookup
        attendance_by_date = {record.date: record for record in athlete_attendance}
        
        # Get practice dates for this roster
        roster_practice_dates = roster_dates_cache[athlete.roster]
        
        # Filter to include skips start date and respect time range
        skips_practice_dates = [d for d in roster_practice_dates if d >= skips_start_date and d <= end_date]
        
        if not skips_practice_dates:
            continue
        
        # Calculate current streak (from most recent backwards)
        current_streak = 0
        
        for practice_date in reversed(skips_practice_dates):
            athlete_record = attendance_by_date.get(practice_date)
            
            if athlete_record:
                skips_count = athlete_record.skips or 0
            else:
                skips_count = 0
            
            # If no skips, continue streak
            if skips_count == 0:
                current_streak += 1
            else:
                # Streak broken
                break
        
        skip_streaks.append({
            'athlete_id': athlete.id,
            'athlete_name': athlete.name,
            'roster': athlete.roster,
            'streak': current_streak
        })
    
    return skip_streaks

def calculate_all_goal_streaks_optimized(users, wellness_by_user, start_date, end_date, selected_groups, all_athletes):
    """Calculate current goal achievement streaks using pre-fetched data"""
    goal_streaks = []
    
    # Create mapping of user names to athletes for group filtering
    athlete_map = {f"{athlete.name}": athlete for athlete in all_athletes}
    
    for user in users:
        # Check if user is in selected groups
        user_full_name = user.get_full_name()
        if user_full_name not in athlete_map:
            continue
        
        athlete = athlete_map[user_full_name]
        if athlete.roster not in selected_groups:
            continue
        
        # Get wellness entries from lookup dictionary and filter by date range
        all_entries = wellness_by_user.get(user.id, [])
        entries = [e for e in all_entries if start_date <= e.date <= end_date]
        
        if not entries:
            continue
        
        # Sort entries by date
        entries_sorted = sorted(entries, key=lambda x: x.date)
        
        # Calculate streaks for both goals
        for goal_type in ['goal1_achieved', 'goal2_achieved']:
            current_streak = 0
            
            # Go through entries in reverse order to find current streak
            for entry in reversed(entries_sorted):
                value = getattr(entry, goal_type, None)
                
                if value:
                    current_streak += 1
                else:
                    # Streak broken
                    break
            
            # Only add if there's an active streak
            if current_streak > 0:
                goal_label = "Goal 1" if goal_type == "goal1_achieved" else "Goal 2"
                goal_streaks.append({
                    'user_id': user.id,
                    'user_name': user.get_full_name(),
                    'goal_type': goal_label,
                    'streak': current_streak
                })
    
    return goal_streaks

