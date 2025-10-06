from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Goal, WellnessEntry
from datetime import datetime, date
from sqlalchemy import desc

wellness_bp = Blueprint('wellness', __name__)

@wellness_bp.route('/wellness_questionnaire', methods=['GET', 'POST'])
@login_required
def wellness_questionnaire():
    if request.method == 'POST':
        # Get form data
        wellness_date = request.form.get('date')
        sleep_hours = request.form.get('sleep_hours')
        sleep_quality = request.form.get('sleep_quality')
        energy_level = request.form.get('energy_level')
        stress_level = request.form.get('stress_level')
        practice_effort = request.form.get('practice_effort')
        hydration = request.form.get('hydration')
        nutrition = request.form.get('nutrition')
        soreness = request.form.get('soreness')
        motivation = request.form.get('motivation')
        mobility = request.form.get('mobility') == 'on'
        
        # Get goal answers
        goal1_achieved = request.form.get('goal1_achieved') == 'on'
        goal2_achieved = request.form.get('goal2_achieved') == 'on'
        
        if wellness_date:
            try:
                entry_date = datetime.strptime(wellness_date, '%Y-%m-%d').date()
                
                # Check if entry already exists for this date
                existing_entry = WellnessEntry.query.filter_by(
                    user_id=current_user.id,
                    date=entry_date
                ).first()
                
                if existing_entry:
                    # Update existing entry
                    existing_entry.sleep_hours = int(sleep_hours) if sleep_hours else None
                    existing_entry.sleep_quality = int(sleep_quality) if sleep_quality else None
                    existing_entry.energy_level = int(energy_level) if energy_level else None
                    existing_entry.stress_level = int(stress_level) if stress_level else None
                    existing_entry.practice_effort = int(practice_effort) if practice_effort else None
                    existing_entry.motivation = int(motivation) if motivation else None
                    existing_entry.hydration = hydration if hydration else None
                    existing_entry.nutrition = nutrition if nutrition else None
                    existing_entry.soreness = soreness if soreness else None
                    existing_entry.mobility = mobility
                    existing_entry.goal1_achieved = goal1_achieved
                    existing_entry.goal2_achieved = goal2_achieved
                    existing_entry.updated_at = datetime.utcnow()
                    
                    flash('Wellness data updated successfully!', 'success')
                else:
                    # Create new entry
                    wellness_entry = WellnessEntry(
                        user_id=current_user.id,
                        date=entry_date,
                        sleep_hours=int(sleep_hours) if sleep_hours else None,
                        sleep_quality=int(sleep_quality) if sleep_quality else None,
                        energy_level=int(energy_level) if energy_level else None,
                        stress_level=int(stress_level) if stress_level else None,
                        practice_effort=int(practice_effort) if practice_effort else None,
                        motivation=int(motivation) if motivation else None,
                        hydration=hydration if hydration else None,
                        nutrition=nutrition if nutrition else None,
                        soreness=soreness if soreness else None,
                        mobility=mobility,
                        goal1_achieved=goal1_achieved,
                        goal2_achieved=goal2_achieved
                    )
                    db.session.add(wellness_entry)
                    flash('Wellness data recorded successfully!', 'success')
                
                db.session.commit()
                return redirect(url_for('wellness.wellness_questionnaire'))
                
            except ValueError:
                flash('Invalid date format', 'error')
            except Exception as e:
                flash(f'Error saving wellness data: {str(e)}', 'error')
                db.session.rollback()
    
    # Get user's active goals for display
    active_goals = Goal.query.filter_by(user_id=current_user.id, is_active=True).all()
    goals_dict = {goal.goal_type: goal.goal_text for goal in active_goals}
    
    return render_template('wellness_questionnaire.html', goals=goals_dict)

@wellness_bp.route('/wellness_dashboard')
@login_required
def wellness_dashboard():
    """Dashboard page to view wellness data over time"""
    # Define available metrics for selection (goals are now separate)
    metrics = {
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
    }
    
    return render_template('wellness_dashboard.html', metrics=metrics)

@wellness_bp.route('/api/wellness_data')
@login_required
def get_wellness_data():
    """API endpoint to get wellness data for graphing"""
    metric = request.args.get('metric')
    user_id = request.args.get('user_id')
    
    if not metric:
        return jsonify({'error': 'Metric parameter is required'}), 400
    
    # If user_id is provided, use that (for coaches viewing athletes)
    # Otherwise use current_user (for athletes viewing their own data)
    target_user_id = int(user_id) if user_id else current_user.id
    
    # Get all wellness entries for the target user, ordered by date
    entries = WellnessEntry.query.filter_by(
        user_id=target_user_id
    ).order_by(WellnessEntry.date).all()
    
    if not entries:
        return jsonify({'error': 'No wellness data found'}), 404
    
    # Get goal text if this is a goal metric
    goal_text = None
    if metric in ['goal1_achieved', 'goal2_achieved']:
        goal_type = 'goal1' if metric == 'goal1_achieved' else 'goal2'
        active_goal = Goal.query.filter_by(
            user_id=target_user_id,
            goal_type=goal_type,
            is_active=True
        ).first()
        if active_goal:
            goal_text = active_goal.goal_text
    
    # Prepare data for the chart
    chart_data = []
    running_score = 0  # For goal tracking
    
    # For mobility, start from tomorrow's date with score 0
    if metric == 'mobility':
        from datetime import date, timedelta
        tomorrow = date.today() + timedelta(days=1)
        
        # Filter entries to only include tomorrow and forward
        entries = [entry for entry in entries if entry.date >= tomorrow]
        
        # Create a starting point for tomorrow
        chart_data.append({
            'date': tomorrow.strftime('%Y-%m-%d'),
            'display_date': tomorrow.strftime('%m/%d'),
            'value': 0,
            'display_value': 'Score: 0 (Starting Point)'
        })
    
    for entry in entries:
        value = getattr(entry, metric, None)
        
        # Convert categorical values to numeric scores for graphing
        if metric in ['hydration', 'nutrition']:
            value_map = {'poor': 1, 'fair': 2, 'good': 3, 'excellent': 4}
            numeric_value = value_map.get(value) if value else None
            display_value = value.capitalize() if value else None
        elif metric == 'soreness':
            value_map = {'none': 0, 'mild': 1, 'moderate': 2, 'severe': 3, 'extreme': 4}
            numeric_value = value_map.get(value) if value else None
            display_value = value.capitalize() if value else None
        elif metric in ['goal1_achieved', 'goal2_achieved', 'mobility']:
            # For goals and mobility, calculate running score like attendance
            # +1 for achieved/completed, -1 for not achieved/not completed
            daily_points = 1 if value else -1
            running_score += daily_points
            numeric_value = running_score
            if metric == 'mobility':
                display_value = f"Score: {running_score} ({'Completed' if value else 'Not Completed'})"
            else:
                display_value = f"Score: {running_score} ({'Achieved' if value else 'Not Achieved'})"
        else:
            # Numeric values
            numeric_value = value
            display_value = str(value) if value is not None else None
        
        chart_data.append({
            'date': entry.date.strftime('%Y-%m-%d'),
            'display_date': entry.date.strftime('%m/%d'),
            'value': numeric_value,
            'display_value': display_value
        })
    
    # Calculate statistics
    values = [d['value'] for d in chart_data if d['value'] is not None]
    
    if values:
        # For goal and mobility metrics, statistics are different since we're tracking running score
        if metric in ['goal1_achieved', 'goal2_achieved', 'mobility']:
            # For mobility, use the filtered entries (today forward)
            # For goals, use all entries
            target_entries = entries if metric != 'mobility' else entries
            achievements = [1 if getattr(entry, metric, None) else 0 for entry in target_entries]
            avg_value = (sum(achievements) / len(achievements)) * 100 if achievements else 0  # Percentage
            min_value = min(values)  # Lowest running score
            max_value = max(values)  # Highest running score
        else:
            avg_value = sum(values) / len(values)
            min_value = min(values)
            max_value = max(values)
    else:
        avg_value = None
        min_value = None
        max_value = None
    
    response_data = {
        'metric': metric,
        'chart_data': chart_data,
        'total_entries': len(entries),
        'statistics': {
            'average': round(avg_value, 1) if avg_value is not None else None,
            'min': min_value,
            'max': max_value,
            'count': len(values)
        }
    }
    
    # Add goal text if available
    if goal_text:
        response_data['goal_text'] = goal_text
    
    return jsonify(response_data)

@wellness_bp.route('/api/goals_data')
@login_required
def get_goals_data():
    """API endpoint to get goals tracking data for graphing"""
    user_id = request.args.get('user_id')
    
    # If user_id is provided, use that (for coaches viewing athletes)
    # Otherwise use current_user (for athletes viewing their own data)
    target_user_id = int(user_id) if user_id else current_user.id
    
    # Get active goals for the user
    goals = Goal.query.filter_by(
        user_id=target_user_id,
        is_active=True
    ).all()
    
    # Get all wellness entries for the target user, ordered by date
    entries = WellnessEntry.query.filter_by(
        user_id=target_user_id
    ).order_by(WellnessEntry.date).all()
    
    if not entries:
        return jsonify({'error': 'No wellness data found'}), 404
    
    # Process data for each goal
    goals_data = []
    
    for goal in goals:
        metric = 'goal1_achieved' if goal.goal_type == 'goal1' else 'goal2_achieved'
        
        # Calculate running score and streak
        chart_data = []
        running_score = 0
        current_streak = 0
        max_streak = 0
        temp_streak = 0
        highest_score = 0
        
        for entry in entries:
            value = getattr(entry, metric, None)
            
            # Calculate running score
            daily_points = 1 if value else -1
            running_score += daily_points
            
            # Track highest score
            if running_score > highest_score:
                highest_score = running_score
            
            # Calculate streak (consecutive achievements)
            if value:
                temp_streak += 1
                if temp_streak > max_streak:
                    max_streak = temp_streak
            else:
                temp_streak = 0
            
            # Current streak is the temp_streak if we're still in it
            if entry == entries[-1]:  # Last entry
                current_streak = temp_streak
            
            chart_data.append({
                'date': entry.date.strftime('%Y-%m-%d'),
                'display_date': entry.date.strftime('%m/%d'),
                'value': running_score,
                'achieved': value,
                'display_value': f"Score: {running_score} ({'Achieved' if value else 'Not Achieved'})"
            })
        
        # Calculate achievement percentage
        achievements = [1 if getattr(entry, metric, None) else 0 for entry in entries]
        achievement_percentage = (sum(achievements) / len(achievements)) * 100 if achievements else 0
        
        goals_data.append({
            'goal_type': goal.goal_type,
            'goal_text': goal.goal_text,
            'chart_data': chart_data,
            'statistics': {
                'current_score': running_score,
                'highest_score': highest_score,
                'current_streak': current_streak,
                'achievement_percentage': round(achievement_percentage, 1),
                'total_entries': len(entries)
            }
        })
    
    return jsonify({
        'goals': goals_data
    })
