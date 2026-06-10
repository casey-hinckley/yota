from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
import os
import urllib.parse

load_dotenv()

from models import db, User

def create_app():
    app = Flask(__name__)
    # WARNING: the fallback key is insecure — always set SECRET_KEY in .env for production
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

    SUPABASE_DB_HOST = os.getenv('SUPABASE_DB_HOST')
    SUPABASE_DB_NAME = os.getenv('SUPABASE_DB_NAME', 'postgres')
    SUPABASE_DB_USER = os.getenv('SUPABASE_DB_USER', 'postgres')
    SUPABASE_DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD')
    SUPABASE_DB_PORT = os.getenv('SUPABASE_DB_PORT', '5432')

    if not SUPABASE_DB_HOST or not SUPABASE_DB_PASSWORD:
        raise RuntimeError("SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD must be set in .env")

    # URL-encode the password so special characters (e.g. @) don't break the URI
    encoded_password = urllib.parse.quote(SUPABASE_DB_PASSWORD, safe='')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{SUPABASE_DB_USER}:{encoded_password}@{SUPABASE_DB_HOST}:{SUPABASE_DB_PORT}/{SUPABASE_DB_NAME}'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {
            'sslmode': 'require',
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000'  # 30 seconds in ms
        },
        'pool_pre_ping': True,   # drops stale connections before use
        'pool_recycle': 300,     # recycle connections after 5 minutes
    }
    print(f"Connecting to Supabase: {SUPABASE_DB_HOST}")

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes import register_routes
    register_routes(app)

    return app

# Module-level app instance required by gunicorn (e.g. `gunicorn app:app`)
app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
