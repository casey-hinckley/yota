from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Goal
from datetime import datetime

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'set_goals':
            # Save user's goals
            goal1_text = request.form.get('goal1_text', '').strip()
            goal2_text = request.form.get('goal2_text', '').strip()
            
            # Deactivate existing goals for this user
            existing_goals = Goal.query.filter_by(user_id=current_user.id, is_active=True).all()
            for goal in existing_goals:
                goal.is_active = False
            
            # Create new goals
            if goal1_text:
                goal1 = Goal(
                    user_id=current_user.id,
                    goal_text=goal1_text,
                    goal_type='goal1',
                    is_active=True
                )
                db.session.add(goal1)
            
            if goal2_text:
                goal2 = Goal(
                    user_id=current_user.id,
                    goal_text=goal2_text,
                    goal_type='goal2',
                    is_active=True
                )
                db.session.add(goal2)
            
            db.session.commit()
            flash('Goals saved successfully!', 'success')
            return redirect(url_for('goals.goals'))
    
    # Get user's active goals
    active_goals = Goal.query.filter_by(user_id=current_user.id, is_active=True).all()
    goals_dict = {goal.goal_type: goal.goal_text for goal in active_goals}
    
    return render_template('goals.html', goals=goals_dict)

@goals_bp.route('/api/goals/<goal_type>', methods=['GET'])
@login_required
def get_goal(goal_type):
    """API endpoint to get a specific goal for the logged-in user"""
    goal = Goal.query.filter_by(user_id=current_user.id, goal_type=goal_type, is_active=True).first()
    
    if goal:
        return jsonify({
            'goal_text': goal.goal_text,
            'created_date': goal.created_date.isoformat()
        })
    else:
        return jsonify({'goal_text': '', 'created_date': None})
