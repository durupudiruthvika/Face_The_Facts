from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# 1. User Table
# utils/db_models.py

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Consent Fields
    consent_signature = db.Column(db.String(150), nullable=False, default="Not Signed")
    consent_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- NEW: Calibration Data ---
    # Default is 0.26 (Standard). We update this after calibration.
    calibration_threshold = db.Column(db.Float, default=0.26)
    is_calibrated = db.Column(db.Boolean, default=False)
    
    # Relationships
    sessions = db.relationship('MonitoringSession', backref='user', lazy=True)
    todos = db.relationship('TodoItem', backref='user', lazy=True)

# ... (Keep MonitoringSession, SessionData, TodoItem exactly as they were) ...

# 2. Monitoring Session (The Summary)


class MonitoringSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    
    # Existing Metrics
    total_blinks = db.Column(db.Integer, default=0)
    avg_ear = db.Column(db.Float, default=0.0)
    avg_stress_score = db.Column(db.Float, default=0.0)
    
    # --- NEW: Interaction Metrics ---
    keyboard_activity = db.Column(db.Integer, default=0) # Total key presses
    mouse_activity = db.Column(db.Integer, default=0)    # Approximate distance moved
    
    gemini_report = db.Column(db.Text, nullable=True) 
    data_points = db.relationship('SessionData', backref='session', lazy=True)

# 3. Session Data (The Graph Points)
class SessionData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('monitoring_session.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    ear_value = db.Column(db.Float)        # Eye Aspect Ratio
    blink_count_snapshot = db.Column(db.Integer)
    detected_emotion = db.Column(db.String(50)) 
    stress_score = db.Column(db.Float)

# 4. NEW: To-Do Item (For the Planner)
class TodoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task = db.Column(db.String(200), nullable=False) # The task description
    due_date = db.Column(db.String(20), nullable=False) # Format: YYYY-MM-DD
    is_completed = db.Column(db.Boolean, default=False)