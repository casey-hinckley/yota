from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required
from models import db, Athlete, SwimTime
from utils import (
    get_athletes_from_data, get_events_from_data, get_courses_from_data,
    get_meets_from_standards, extract_athlete_age, get_athlete_gender,
    get_time_standards_for_event, get_eligible_age_groups, determine_cuts_achieved,
    get_next_cut, calculate_time_improvement_analysis, parse_time
)
import pandas as pd

swim_analysis_bp = Blueprint('swim_analysis', __name__)

@swim_analysis_bp.route('/swim_analysis')
@login_required
def swim_analysis():
    """Main swim analysis page"""
    with current_app.app_context():
        athletes = get_athletes_from_data()
        events = get_events_from_data()
        courses = get_courses_from_data()
        meets = get_meets_from_standards()
    
    return render_template('swim_analysis.html', 
                         athletes=athletes, 
                         events=events, 
                         courses=courses,
                         meets=meets)

@swim_analysis_bp.route('/api/swim_data')
@login_required
def get_swim_data():
    """API endpoint to get swim data for selected athlete, course, and event"""
    athlete_id = request.args.get('athlete_id')
    athlete_name = request.args.get('athlete')
    course = request.args.get('course')
    event = request.args.get('event')
    selected_meet = request.args.get('meet', '')
    
    if not all([course, event]) or not (athlete_id or athlete_name):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Convert course code to database format
    course_mapping = {'Y': 'SCY', 'L': 'LCM', 'M': 'SCM'}
    course_name = course_mapping.get(course, course)
    
    with current_app.app_context():
        # Get athlete from database - support both ID and name
        if athlete_id:
            athlete_record = Athlete.query.get(int(athlete_id))
        else:
            athlete_record = Athlete.query.filter_by(name=athlete_name).first()
            
        if not athlete_record:
            return jsonify({'error': 'Athlete not found'}), 404
        
        athlete = athlete_record.name
        
        # Get swim times from database
        swim_times = SwimTime.query.filter_by(
            athlete_id=athlete_record.id,
            event=event,
            course=course_name
        ).order_by(SwimTime.meet_date).all()
        
        if not swim_times:
            return jsonify({'error': 'No data found for selected criteria'}), 404
    
    # Convert to DataFrame-like structure for compatibility
    filtered_data = []
    for swim_time in swim_times:
        filtered_data.append({
            'Name': athlete,
            'Event': swim_time.event,
            'Best Time': swim_time.best_time,
            'time_seconds': swim_time.time_seconds,
            'Date': swim_time.meet_date.strftime('%m/%d/%Y') if swim_time.meet_date else '',
            'Meet Name': swim_time.meet_name or '',
            'P/F/T': swim_time.prelim_final or '',
            'Rank': swim_time.rank
        })
    
    if not filtered_data:
        return jsonify({'error': 'No data found for selected criteria'}), 404
    
    # Get athlete info from database record
    athlete_age = athlete_record.age
    athlete_gender = athlete_record.gender
    
    # Check if we have required athlete information
    if not athlete_age or not athlete_gender:
        # Try to extract from athlete name as fallback
        if '(' in athlete:
            athlete_age = athlete_age or extract_athlete_age(athlete)
            athlete_gender = athlete_gender or get_athlete_gender(athlete)
    
    # Get time standards - will return empty if age/gender missing
    standards_df = get_time_standards_for_event(event, course_name, athlete_gender, athlete_age) if athlete_age and athlete_gender else pd.DataFrame()
    
    # Debug information
    eligible_age_groups = get_eligible_age_groups(athlete_age)
    
    # Get best time
    best_time_record = min(filtered_data, key=lambda x: x['time_seconds'] if x['time_seconds'] else float('inf'))
    best_time_seconds = best_time_record['time_seconds']
    
    # Determine cuts achieved and next cut
    achieved_cuts = determine_cuts_achieved(best_time_seconds, standards_df)
    next_cut = get_next_cut(best_time_seconds, standards_df)
    
    # Filter standards by selected meet if specified
    if selected_meet and not standards_df.empty:
        meet_standards = standards_df[standards_df['Meet'] == selected_meet]
    else:
        meet_standards = standards_df

    display_next_cut = next_cut
    if selected_meet and not meet_standards.empty:
        meet_cuts = meet_standards  # already filtered to selected_meet above
        
        if not meet_cuts.empty:
            meet_cuts['distance'] = abs(meet_cuts['time_seconds'] - best_time_seconds)
            closest_meet_cut = meet_cuts.loc[meet_cuts['distance'].idxmin()]
            
            # If this cut is unachieved, use it as the display cut
            if closest_meet_cut['time_seconds'] < best_time_seconds:
                display_next_cut = {
                    'meet': str(closest_meet_cut['Meet']),
                    'age_group': str(closest_meet_cut['Age Group']),
                    'time': str(closest_meet_cut['Time']),
                    'time_seconds': float(closest_meet_cut['time_seconds']) if pd.notna(closest_meet_cut['time_seconds']) else None,
                    'distance_seconds': float(best_time_seconds - closest_meet_cut['time_seconds']) if pd.notna(closest_meet_cut['time_seconds']) else None,
                    'distance_percentage': float(((best_time_seconds - closest_meet_cut['time_seconds']) / best_time_seconds) * 100) if pd.notna(closest_meet_cut['time_seconds']) else None,
                    'achieved': False
                }
            else:
                # If this cut is achieved, show distance past it
                display_next_cut = {
                    'meet': str(closest_meet_cut['Meet']),
                    'age_group': str(closest_meet_cut['Age Group']),
                    'time': str(closest_meet_cut['Time']),
                    'time_seconds': float(closest_meet_cut['time_seconds']) if pd.notna(closest_meet_cut['time_seconds']) else None,
                    'distance_seconds': float(best_time_seconds - closest_meet_cut['time_seconds']) if pd.notna(closest_meet_cut['time_seconds']) else None,
                    'distance_percentage': float(((best_time_seconds - closest_meet_cut['time_seconds']) / closest_meet_cut['time_seconds']) * 100) if pd.notna(closest_meet_cut['time_seconds']) else None,
                    'beyond_fastest': True,
                    'achieved': True
                }
    
    # Prepare data for chart
    def map_type(pft):
        # 'T' (Time Trial) is not mapped and will fall through to the raw value
        return {'P': 'Prelims', 'F': 'Finals'}.get(str(pft).strip().upper(), str(pft))

    chart_data = []
    for record in filtered_data:
        chart_data.append({
            'date': record['Date'],
            'time': str(record['Best Time']),
            'time_seconds': float(record['time_seconds']) if record['time_seconds'] else None,
            'type': map_type(record['P/F/T']),
            'meet': str(record['Meet Name'])
        })
    
    # Find best time
    best_time_info = {
        'time': str(best_time_record['Best Time']),
        'date': best_time_record['Date'],
        'meet': str(best_time_record['Meet Name']),
        'type': map_type(best_time_record['P/F/T'])
    }
    
    # CSV-based legacy function; returns None if cleaned_swim_data.csv or
    # Swimmer_Attendance_Percentages.csv are not present
    attendance_analysis = calculate_time_improvement_analysis(event, course, athlete)
    
    return jsonify({
        'chart_data': chart_data,
        'best_time': best_time_info,
        'total_swims': int(len(filtered_data)),
        'achieved_cuts': achieved_cuts,
        'next_cut': display_next_cut,
        'attendance_analysis': attendance_analysis,
        'athlete_age': int(athlete_age) if athlete_age is not None else None,
        'athlete_gender': str(athlete_gender) if athlete_gender is not None else None,
        # TODO: remove debug_info before production or gate it behind a flag
        'debug_info': {
            'eligible_age_groups': eligible_age_groups,
            'total_standards_found': len(standards_df),
            'standards_available': [{'meet': str(row['Meet']), 'age_group': str(row['Age Group']), 'time': str(row['Time'])} for _, row in standards_df.head(5).iterrows()],
            'next_cut_debug': {
                'next_cut_meet': display_next_cut['meet'] if display_next_cut else None,
                'selected_meet': selected_meet,
                'next_cut_for_chart_meet': display_next_cut['meet'] if display_next_cut else None,
                'best_time_seconds': float(best_time_seconds) if best_time_seconds is not None else None
            }
        }
    })
