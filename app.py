from flask import Flask
from flask_migrate import Migrate

from auth_routes import auth_routes
from config import Config
from models import db
from note_routes import note_routes
from shift_routes import shift_routes


migrate = Migrate()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(auth_routes)
    app.register_blueprint(note_routes)
    app.register_blueprint(shift_routes)

    return app


if __name__ == "__main__":
    create_app().run(port=5555, debug=True)
