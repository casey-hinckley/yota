from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(20), nullable=False, default='coach')  # 'coach', 'admin', etc.
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))  # 'Male' or 'Female'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def check_password(self, password):
        """Check if the provided password matches the stored password"""
        # Based on add_coaches.py, passwords are stored as plain text
        return self.password_hash == password
    
    def set_password(self, password):
        """Set the password (stored as plain text for now)"""
        self.password_hash = password
    
    def get_full_name(self):
        """Return the user's full name"""
        return f"{self.first_name} {self.last_name}".strip()

class Athlete(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    preferred_name = db.Column(db.String(50))  # Nickname/preferred first name for attendance
    age = db.Column(db.Integer)
    birthday = db.Column(db.Date)
    roster = db.Column(db.String(100))
    gender = db.Column(db.String(10))  # 'Male' or 'Female'

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    goal_text = db.Column(db.String(500), nullable=False)
    goal_type = db.Column(db.String(50), nullable=False)  # 'goal1' or 'goal2'
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref='goals')

class SwimTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athlete.id'), nullable=False)
    event = db.Column(db.String(50), nullable=False)
    best_time = db.Column(db.String(20), nullable=False)
    time_seconds = db.Column(db.Float)  # Converted time for comparison
    course = db.Column(db.String(10))  # SCY, LCM, SCM
    meet_name = db.Column(db.String(200))
    meet_date = db.Column(db.Date)
    prelim_final = db.Column(db.String(10))  # P, F, T
    rank = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    athlete = db.relationship('Athlete', backref='swim_times')

class WellnessEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    sleep_hours = db.Column(db.Integer)
    sleep_quality = db.Column(db.Integer)  # 1-5 scale
    energy_level = db.Column(db.Integer)  # 1-10 scale
    stress_level = db.Column(db.Integer)  # 1-10 scale
    practice_effort = db.Column(db.Integer)  # 1-10 scale
    motivation = db.Column(db.Integer)  # 1-10 scale
    hydration = db.Column(db.String(50))
    nutrition = db.Column(db.String(50))
    soreness = db.Column(db.String(50))
    mobility = db.Column(db.Boolean, default=False)  # Did they do mobility/rehab routine
    goal1_achieved = db.Column(db.Boolean, default=False)
    goal2_achieved = db.Column(db.Boolean, default=False)
    additional_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='wellness_entries')

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athlete.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'present', 'absent', 'sick', etc.
    attendance_value = db.Column(db.Float, default=1.0)  # 0.0 to 1.0 for partial attendance
    skips = db.Column(db.Integer, default=0)  # Number of skips for this athlete on this date
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    athlete = db.relationship('Athlete', backref='attendance_records')

