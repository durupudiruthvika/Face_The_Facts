from flask import Flask, render_template, redirect, url_for, request, flash
from config import Config
from utils.db_models import db, User, MonitoringSession
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime
from collections import Counter
from utils.ai_generator import generate_wellbeing_report
from utils.db_models import SessionData # Ensure this is imported
from utils.db_models import TodoItem # Add TodoItem
import os
# --- NEW IMPORTS FOR CHATBOT ---
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Key for Chatbot
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

app = Flask(__name__)
app.config.from_object(Config)

# Extensions
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
def home():
    # If user is already logged in, send them to dashboard directly
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Otherwise, show the new Landing Page
    return render_template('home.html')

# app.py (Update the dashboard route)

@app.route('/dashboard')
@login_required
def dashboard():
    # 1. Fetch Data
    recent_sessions = MonitoringSession.query.filter_by(user_id=current_user.id)\
        .order_by(MonitoringSession.start_time.desc()).limit(3).all()
    
    upcoming_todos = TodoItem.query.filter_by(user_id=current_user.id, is_completed=False)\
        .order_by(TodoItem.due_date).limit(5).all()
        
    # 2. Calculate Plant Health (Gamification Logic)
    plant_health = 100 # Default start
    plant_status = "Radiant"
    
    if recent_sessions:
        # Simple Algorithm: Start at 100, subtract stress
        last_stress = recent_sessions[0].avg_stress_score # Assuming you have this, or use blink rate proxy
        last_blinks = recent_sessions[0].total_blinks
        
        # If blinks are low (< 15), penalize health
        if last_blinks < 15:
            plant_health -= 30
        
        # If stress is high (proxy: low EAR or just use a placeholder calculation if stress_score is 0)
        # For demo, let's simulate variation based on blinks
        if last_blinks > 50: # Very active/stressed eyes
            plant_health -= 20
            
        # Cap values
        plant_health = max(0, min(100, plant_health))
        
        # Determine Status Label
        if plant_health > 80: plant_status = "Radiant"
        elif plant_health > 50: plant_status = "Healthy"
        elif plant_health > 20: plant_status = "Thirsty"
        else: plant_status = "Withered"

    return render_template('dashboard.html', 
                           sessions=recent_sessions, 
                           todos=upcoming_todos,
                           plant_health=plant_health,
                           plant_status=plant_status)

# --- HISTORY PAGE (Full Records) ---
@app.route('/history')
@login_required
def history():
    # Fetch ALL sessions
    all_sessions = MonitoringSession.query.filter_by(user_id=current_user.id)\
        .order_by(MonitoringSession.start_time.desc()).all()
    return render_template('history.html', sessions=all_sessions)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        signature = request.form.get('signature') # NEW: Get Signature
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        # Hash password and save
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Create User with Signature
        new_user = User(
            username=username, 
            email=email, 
            password=hashed_pw,
            consent_signature=signature,  # SAVE SIGNATURE
            consent_date=datetime.utcnow()
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Log them in immediately
        login_user(new_user)
        
        flash('Account created! Let\'s calibrate your eyes.', 'success')
        # Redirect to Calibration instead of Login
        return redirect(url_for('calibration'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check email and password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- NEW MONITORING ROUTES ---

@app.route('/monitor')
@login_required
def monitor():
    # Create a new session record
    new_session = MonitoringSession(user_id=current_user.id)
    db.session.add(new_session)
    db.session.commit()
    
    # Store session ID in Flask session (cookie) to track data
    from flask import session as flask_session
    flask_session['current_session_id'] = new_session.id
    
    return render_template('monitor.html')

@app.route('/api/update_session', methods=['POST'])
@login_required
def update_session():
    from flask import session as flask_session
    from utils.db_models import SessionData

    data = request.json
    session_id = flask_session.get('current_session_id')
    
    if session_id:
        current_sess = MonitoringSession.query.get(session_id)
        if current_sess:
            # 1. Update Summary Metrics
            current_sess.total_blinks = data.get('blinks', 0)
            current_sess.keyboard_activity = data.get('keys', 0)
            current_sess.mouse_activity = data.get('mouse', 0)
            
            # FIX: Save the Average EAR
            current_sess.avg_ear = data.get('session_avg_ear', 0.0)
            
            # 2. Log Granular Data
            emotion = data.get('emotion', 'Neutral')
            
            new_data = SessionData(
                session_id=session_id,
                blink_count_snapshot=data.get('blinks', 0),
                detected_emotion=emotion,
                stress_score=0.0,
                # FIX: Save the snapshot EAR for graphs
                ear_value=data.get('current_ear', 0.0)
            )
            db.session.add(new_data)
            db.session.commit()
            return {'status': 'success'}, 200
            
    return {'status': 'error'}, 400

@app.route('/generate_report')
@login_required
def generate_report():
    from flask import session as flask_session
    
    # 1. Get the current session
    session_id = flask_session.get('current_session_id')
    if not session_id:
        return redirect(url_for('dashboard'))
    
    current_sess = MonitoringSession.query.get(session_id)
    
    # 2. End the session (mark time)
    if not current_sess.end_time:
        current_sess.end_time = datetime.utcnow()
    
    # Calculate Duration
    duration = (current_sess.end_time - current_sess.start_time).seconds / 60
    duration = round(duration, 2)

    # 3. Analyze Data Points (Emotions & Charts)
    # Fetch all granular data for this session, SORTED BY TIME
    all_data = SessionData.query.filter_by(session_id=session_id).order_by(SessionData.timestamp).all()
    
    emotion_list = [d.detected_emotion for d in all_data if d.detected_emotion]
    
    if emotion_list:
        # Find most common emotion
        emotion_counts = Counter(emotion_list)
        dominant_emotion = emotion_counts.most_common(1)[0][0]
        emotion_summary = str(dict(emotion_counts))
    else:
        dominant_emotion = "Neutral"
        emotion_summary = "No distinct emotions detected."

    # 4. Call Gemini AI
    # inside app.py
    ai_text = generate_wellbeing_report(
        duration_minutes=duration,
        total_blinks=current_sess.total_blinks,
        avg_ear=current_sess.avg_ear, 
        dominant_emotion=dominant_emotion,
        emotion_breakdown=emotion_summary,
        # Make sure these two lines are there:
        total_keys=current_sess.keyboard_activity,
        total_mouse=current_sess.mouse_activity
    )

    # --- NEW: Prepare Data for Charts ---
    # Extract timestamps (X-axis) and blink counts (Y-axis)
    timestamps = [d.timestamp.strftime('%H:%M:%S') for d in all_data]
    blinks_over_time = [d.blink_count_snapshot for d in all_data]
    
    chart_data = {
        "timestamps": timestamps,
        "blinks": blinks_over_time
    }
    
    # 5. Save to DB
    current_sess.gemini_report = ai_text
    db.session.commit()
    
    # 6. Clear session cookie
    flask_session.pop('current_session_id', None)
    
    # 7. Return Template with Chart Data
    return render_template('report.html', 
                           session=current_sess, 
                           report_html=ai_text, 
                           chart_data=chart_data)


# --- TO-DO LIST ROUTES ---
@app.route('/planner', methods=['GET', 'POST'])
@login_required
def todo_list():
    if request.method == 'POST':
        task = request.form.get('task')
        due_date = request.form.get('due_date')
        
        if task and due_date:
            new_todo = TodoItem(user_id=current_user.id, task=task, due_date=due_date)
            db.session.add(new_todo)
            db.session.commit()
            flash('Task added to your schedule!', 'success')
        return redirect(url_for('todo_list'))

    # Fetch user's todos sorted by date
    todos = TodoItem.query.filter_by(user_id=current_user.id).order_by(TodoItem.due_date).all()
    return render_template('todo.html', todos=todos)

@app.route('/planner/delete/<int:id>')
@login_required
def delete_todo(id):
    todo = TodoItem.query.get_or_404(id)
    if todo.user_id == current_user.id:
        db.session.delete(todo)
        db.session.commit()
    return redirect(url_for('todo_list'))

@app.route('/planner/toggle/<int:id>')
@login_required
def toggle_todo(id):
    todo = TodoItem.query.get_or_404(id)
    if todo.user_id == current_user.id:
        todo.is_completed = not todo.is_completed
        db.session.commit()
    return redirect(url_for('todo_list'))

# --- PROFILE ROUTE ---
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        
        current_user.username = new_username
        current_user.email = new_email
        db.session.commit()
        flash('Profile details updated!', 'success')
        
    return render_template('profile.html')

# --- NEW: View Past Report Route ---
@app.route('/report/<int:session_id>')
@login_required
def view_report(session_id):
    # 1. Fetch Session safely
    session = MonitoringSession.query.get_or_404(session_id)
    
    # Security Check: Ensure this session belongs to the current user
    if session.user_id != current_user.id:
        return redirect(url_for('dashboard'))
    
    # 2. Re-construct Chart Data
    all_data = SessionData.query.filter_by(session_id=session_id).order_by(SessionData.timestamp).all()
    
    timestamps = [d.timestamp.strftime('%H:%M:%S') for d in all_data]
    blinks_over_time = [d.blink_count_snapshot for d in all_data]
    
    chart_data = {
        "timestamps": timestamps,
        "blinks": blinks_over_time
    }
    
    # 3. Render the existing report template
    return render_template('report.html', 
                           session=session, 
                           report_html=session.gemini_report, 
                           chart_data=chart_data)

@app.route('/calibration')
@login_required
def calibration():
    return render_template('calibration.html')

@app.route('/api/save_calibration', methods=['POST'])
@login_required
def save_calibration():
    data = request.json
    new_threshold = data.get('threshold')
    
    if new_threshold:
        current_user.calibration_threshold = float(new_threshold)
        current_user.is_calibrated = True
        db.session.commit()
        flash('Calibration saved successfully!', 'success')
        return {'status': 'saved'}, 200
    return {'status': 'error'}, 400

 # --- CHATBOT API (FIXED) ---
@app.route('/api/chat_with_coach', methods=['POST'])
@login_required
def chat_with_coach():
    user_message = request.json.get('message')
    
    # 1. Gather User Context
    recent_sessions = MonitoringSession.query.filter_by(user_id=current_user.id)\
        .order_by(MonitoringSession.start_time.desc()).limit(5).all()
    
    total_sessions = len(recent_sessions)
    avg_blinks = 0
    if total_sessions > 0:
        avg_blinks = sum(s.total_blinks for s in recent_sessions) / total_sessions

    # 2. Construct Prompt
    system_context = f"""
    You are 'FaceTheFacts Coach', a helpful AI assistant.
    
    USER CONTEXT:
    - Name: {current_user.username}
    - Recent Sessions: {total_sessions}
    - Avg Blinks (Recent): {avg_blinks:.1f}
    
    Instructions: Answer briefly and supportively.
    """
    
    # 3. Send to Gemini
    try:
        # Use the same model as the report generator
        model = genai.GenerativeModel('gemini-2.5-flash')
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_context]},
            {"role": "model", "parts": ["Understood."]}
        ])
        
        response = chat.send_message(user_message)
        return {'reply': response.text}, 200
    except Exception as e:
        print(f"Chat Error: {e}")
        # Return the specific error to the console so you can debug it if it happens again
        return {'reply': f"AI Error: {str(e)}"}, 200
    
    # --- MANAGER / ADMIN DASHBOARD ---
@app.route('/manager')
def manager_dashboard():
    # NOTE: For a demo, we simulate team data to show the "Big Picture" capabilities.
    # In a real deployment, this would query all users in the database.
    
    import random
    
    # 1. Mock Team Stats
    team_health_score = 82 # 0-100
    active_employees = 42
    burnout_risk_count = 3
    
    # 2. Mock Employee List
    employees = [
        {"name": "Sarah J.", "role": "Frontend Dev", "status": "Flow State", "stress": 15, "blinks": 18},
        {"name": "Mike R.", "role": "Backend Dev", "status": "Stressed", "stress": 78, "blinks": 8},
        {"name": "Jessica T.", "role": "Designer", "status": "Balanced", "stress": 42, "blinks": 14},
        {"name": "David K.", "role": "Product Mgr", "status": "Fatigued", "stress": 65, "blinks": 10},
        {"name": "Emily W.", "role": "QA Tester", "status": "Flow State", "stress": 20, "blinks": 22},
    ]
    
    # 3. Data for Charts
    # Hourly Stress Average (9AM to 5PM)
    hourly_stress = [20, 25, 30, 45, 60, 55, 40, 35, 25] 
    hours = ["9AM", "10AM", "11AM", "12PM", "1PM", "2PM", "3PM", "4PM", "5PM"]
    
    return render_template('manager.html', 
                           health_score=team_health_score,
                           active=active_employees,
                           risk_count=burnout_risk_count,
                           employees=employees,
                           hourly_stress=hourly_stress,
                           hours=hours)

@app.route('/gestures')
@login_required
def gestures():
    return render_template('gestures.html')

# --- Run ---
if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('database/wellbeing.db'):
            db.create_all()
    app.run(debug=True)