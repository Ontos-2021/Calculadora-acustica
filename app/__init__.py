from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'acoustic-calculator-secret-key'

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
