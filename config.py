import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-84758473'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///storage.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload settings
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024  # 5GB global limit per request

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # HTTPS Enforcement
    ENV = os.environ.get('FLASK_ENV', 'development')
    SESSION_COOKIE_SECURE = (ENV == 'production')
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "1000000 per day"
    RATELIMIT_STORAGE_URL = "memory://"
