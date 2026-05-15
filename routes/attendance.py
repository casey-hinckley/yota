from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Athlete, Attendance
from datetime import datetime, date
import json

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('/attendance')
@login_required
def attendance():
    """Attendance page for coaches"""
    # Check if user is a coach
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    with current_app.app_context():
        # Show all athletes, not just those with attendance records
        athletes = db.session.query(Athlete).all()
        
        # Get unique roster groups for filtering
        rosters = db.session.query(Athlete.roster).filter(
            Athlete.roster.isnot(None),
            Athlete.roster != ''
        ).distinct().order_by(Athlete.roster).all()
        roster_list = [roster[0] for roster in rosters if roster[0]]
    
    return render_template('attendance.html', athletes=athletes, rosters=roster_list)

@attendance_bp.route('/api/attendance/<date_str>')
@login_required
def get_attendance(date_str):
    """Get attendance records for a specific date"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    # Get roster filter from query parameters
    roster_filter = request.args.get('roster', '')
    
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    with current_app.app_context():
        # Get all athletes, not just those with attendance records
        athletes_query = db.session.query(Athlete)
        
        # Apply roster filter if specified
        if roster_filter:
            athletes_query = athletes_query.filter(Athlete.roster == roster_filter)
        
        athletes_with_attendance = athletes_query.all()
        
        # Get existing attendance records for this date
        attendance_records = Attendance.query.filter_by(date=attendance_date).all()
        
        # Create a dictionary for quick lookup
        attendance_dict = {record.athlete_id: record for record in attendance_records}
        
        # Build response — all athletes are included; missing records default to absent/0
        attendance_data = []
        for athlete in athletes_with_attendance:
            record = attendance_dict.get(athlete.id)
            attendance_data.append({
                'athlete_id': athlete.id,
                'athlete_name': athlete.name,
                'roster': athlete.roster or '',
                'status': record.status if record else 'absent',
                'attendance_value': record.attendance_value if record else 0.0,
                'skips': record.skips if record else 0,
                'notes': record.notes if record else ''
            })
        
        # Sort by athlete name for consistent display
        attendance_data.sort(key=lambda x: x['athlete_name'])
    
    return jsonify({
        'date': date_str,
        'roster_filter': roster_filter,
        'attendance': attendance_data
    })

@attendance_bp.route('/api/attendance', methods=['POST'])
@login_required
def update_attendance():
    """Update attendance record for an athlete on a specific date"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    data = request.get_json()
    athlete_id = data.get('athlete_id')
    date_str = data.get('date')
    status = data.get('status')
    attendance_value = data.get('attendance_value', 1.0)
    skips = data.get('skips', 0)
    notes = data.get('notes', '')
    
    if not all([athlete_id, date_str, status]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    with current_app.app_context():
        # Check if athlete exists
        athlete = Athlete.query.get(athlete_id)
        if not athlete:
            return jsonify({'error': 'Athlete not found'}), 404
        
        # Check if attendance record already exists
        existing_record = Attendance.query.filter_by(
            athlete_id=athlete_id, 
            date=attendance_date
        ).first()
        
        if existing_record:
            # Update existing record
            existing_record.status = status
            existing_record.attendance_value = attendance_value
            existing_record.skips = skips
            existing_record.notes = notes
            existing_record.updated_at = datetime.utcnow()
        else:
            # Create new record
            new_record = Attendance(
                athlete_id=athlete_id,
                date=attendance_date,
                status=status,
                attendance_value=attendance_value,
                skips=skips,
                notes=notes
            )
            db.session.add(new_record)
        
        try:
            db.session.commit()
            return jsonify({'success': True, 'message': 'Attendance updated successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500

@attendance_bp.route('/api/attendance/skips', methods=['POST'])
@login_required
def update_skips():
    """Update skips count for an athlete on a specific date"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    data = request.get_json()
    athlete_id = data.get('athlete_id')
    date_str = data.get('date')
    skips = data.get('skips', 0)
    
    if not all([athlete_id, date_str]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    with current_app.app_context():
        # Check if athlete exists
        athlete = Athlete.query.get(athlete_id)
        if not athlete:
            return jsonify({'error': 'Athlete not found'}), 404
        
        # Check if attendance record already exists
        existing_record = Attendance.query.filter_by(
            athlete_id=athlete_id, 
            date=attendance_date
        ).first()
        
        if existing_record:
            # Update existing record's skips
            existing_record.skips = skips
            existing_record.updated_at = datetime.utcnow()
        else:
            # status and attendance_value are non-nullable, so provide safe defaults
            new_record = Attendance(
                athlete_id=athlete_id,
                date=attendance_date,
                status='absent',
                attendance_value=0.0,
                skips=skips,
                notes=''
            )
            db.session.add(new_record)
        
        try:
            db.session.commit()
            return jsonify({'success': True, 'message': 'Skips updated successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500

@attendance_bp.route('/api/attendance/delete', methods=['POST'])
@login_required
def delete_attendance():
    """Delete attendance record for an athlete on a specific date"""
    if current_user.user_type != 'coach':
        return jsonify({'error': 'Access denied. Coaches only.'}), 403
    
    data = request.get_json()
    athlete_id = data.get('athlete_id')
    date_str = data.get('date')
    
    if not all([athlete_id, date_str]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    with current_app.app_context():
        # Find and delete the record
        record = Attendance.query.filter_by(
            athlete_id=athlete_id, 
            date=attendance_date
        ).first()
        
        if record:
            db.session.delete(record)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Attendance record deleted'})
        else:
            return jsonify({'error': 'Record not found'}), 404
