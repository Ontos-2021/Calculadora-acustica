from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
