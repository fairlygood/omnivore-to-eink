from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from config import Config
import logging

limiter = Limiter(get_remote_address, storage_uri="memory://")
socketio = SocketIO()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app)
    limiter.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    csrf.init_app(app)

    # Configure logging
    logging.basicConfig(level=app.config['LOG_LEVEL'])
    app.logger.setLevel(app.config['LOG_LEVEL'])

    # Adjust werkzeug logger
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app