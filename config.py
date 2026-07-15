# config.py
import os

class Config:
    # Secret key for session management (keep this safe in production)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-facethefacts-123'
    
    # Database configuration (SQLite for now)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database/wellbeing.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False