from flask import Blueprint

def register_routes(app):
    """Register all route blueprints with the Flask app"""
    from .auth import auth_bp
    from .athletes import athletes_bp
    from .swim_analysis import swim_analysis_bp
    from .goals import goals_bp
    from .wellness import wellness_bp
    from .attendance import attendance_bp
    from .rankings import rankings_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(athletes_bp)
    app.register_blueprint(swim_analysis_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(wellness_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(rankings_bp)
