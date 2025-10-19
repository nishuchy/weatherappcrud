from flask import Flask
from app.routes.role_routes import role_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(role_bp)
    return app
