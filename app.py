from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
import os
import urllib.parse

# Load environment variables
load_dotenv()

# Import models and database
from models import db, User

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

    # Supabase Database Configuration
    SUPABASE_DB_HOST = os.getenv('SUPABASE_DB_HOST')
    SUPABASE_DB_NAME = os.getenv('SUPABASE_DB_NAME', 'postgres')
    SUPABASE_DB_USER = os.getenv('SUPABASE_DB_USER', 'postgres')
    SUPABASE_DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD')
    SUPABASE_DB_PORT = os.getenv('SUPABASE_DB_PORT', '5432')

    # Use the exact same Supabase connection as the working routes
    if SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD:
        # URL encode the password to handle special characters like @
        encoded_password = urllib.parse.quote(SUPABASE_DB_PASSWORD, safe='')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{SUPABASE_DB_USER}:{encoded_password}@{SUPABASE_DB_HOST}:{SUPABASE_DB_PORT}/{SUPABASE_DB_NAME}'
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {
                'sslmode': 'require',
                'connect_timeout': 10,
                'options': '-c statement_timeout=30000'
            },
            'pool_pre_ping': True,  # Verify connections before using them
            'pool_recycle': 300,  # Recycle connections after 5 minutes
        }
        print(f"🔗 Connecting to Supabase: {SUPABASE_DB_HOST}")
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///athlete_metrics.db'
        print("🔗 Using SQLite database")

    # Initialize database with app
    db.init_app(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register all route blueprints
    from routes import register_routes
    register_routes(app)

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
