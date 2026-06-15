from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS
from mongoengine.connection import ConnectionFailure
from extensions import db
from routes import main_bp
from routes.auth import auth_bp
from routes.tasks import tasks_bp
from routes.preferences import preferences_bp
from routes.workspace import workspace_bp
from routes.task_group import task_group_bp
from routes.user import user_bp
from config import Config


app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS for all routes (needed for Flutter web)
CORS(app, resources={r"/*": {"origins": "*"}})

# MongoDB connection error handler
@app.errorhandler(ConnectionFailure)
def handle_mongodb_connection_error(error):
    app.logger.error(f"MongoDB Connection Error: {error}")
    return jsonify({
        "error": "Database connection error",
        "message": "Could not connect to the database. Please try again later."
    }), 500

# initialize extensions
try:
    db.init_app(app)
    # Test connection
    with app.app_context():
        db.get_db()
    app.logger.info("✅ Connected to MongoDB successfully")
except ConnectionFailure as e:
    app.logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# register routes
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(tasks_bp)
app.register_blueprint(preferences_bp)
app.register_blueprint(workspace_bp, url_prefix="/api")
app.register_blueprint(task_group_bp, url_prefix="/api")
app.register_blueprint(user_bp, url_prefix="/user")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
