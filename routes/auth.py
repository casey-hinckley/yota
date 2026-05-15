from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Athlete
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        if current_user.user_type != 'coach':
            # Athlete names in the Athlete table may differ from the User's stored name
            # (e.g. preferred names, middle names), so we try three progressively looser strategies.
            athlete = None

            # Strategy 1: Exact full-name match
            athlete = Athlete.query.filter(
                Athlete.name == current_user.get_full_name()
            ).first()

            # Strategy 2: preferred_name matches first name + last name substring
            if not athlete:
                athlete = Athlete.query.filter(
                    Athlete.preferred_name == current_user.first_name,
                    Athlete.name.like(f'%{current_user.last_name}%')
                ).first()

            # Strategy 3: partial match on both first and last name (last resort)
            if not athlete:
                athlete = Athlete.query.filter(
                    Athlete.name.like(f'%{current_user.first_name}%{current_user.last_name}%')
                ).first()
            
            if athlete:
                return redirect(url_for('athletes.athlete_detail', athlete_id=athlete.id))
            else:
                # If no athlete record found, go to goals page for athletes
                return redirect(url_for('goals.goals'))
        else:
            return redirect(url_for('athletes.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        if not username or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.is_active:
                # NOTE: last_login is not a column on the User model — this line has no effect
                user.last_login = datetime.utcnow()
                db.session.commit()
                login_user(user, remember=remember)

                next_page = request.args.get('next')
                # Reject absolute URLs in `next` to prevent open-redirect attacks
                if not next_page or not next_page.startswith('/'):
                    if user.user_type != 'coach':
                        # Same three-strategy matching as above
                        athlete = None

                        athlete = Athlete.query.filter(
                            Athlete.name == user.get_full_name()
                        ).first()

                        if not athlete:
                            athlete = Athlete.query.filter(
                                Athlete.preferred_name == user.first_name,
                                Athlete.name.like(f'%{user.last_name}%')
                            ).first()

                        if not athlete:
                            athlete = Athlete.query.filter(
                                Athlete.name.like(f'%{user.first_name}%{user.last_name}%')
                            ).first()

                        if athlete:
                            next_page = url_for('athletes.athlete_detail', athlete_id=athlete.id)
                        else:
                            next_page = url_for('goals.goals')
                    else:
                        next_page = url_for('athletes.index')
                
                flash(f'Welcome back, {user.first_name}!', 'success')
                return redirect(next_page)
            else:
                flash('Your account has been deactivated. Please contact an administrator.', 'error')
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """Display user profile"""
    return render_template('auth/profile.html', user=current_user)
