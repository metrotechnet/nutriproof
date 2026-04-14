from flask import Flask, render_template, redirect
import os, sys, json
from waitress import serve

# When running as a PyInstaller bundle, resolve paths relative to the bundle
if getattr(sys, 'frozen', False):
    _bundle_dir = sys._MEIPASS
else:
    _bundle_dir = os.path.dirname(os.path.abspath(__file__))

from api.extract_tables import OCRDocument
from api.task_mngr import AsyncTaskManager
from api.clean_mngr import CleanManager

from api.routes.project_routes import project_bp
from api.routes.document_routes import document_bp
from api.routes.ocr_routes import ocr_bp
from api.routes.data_routes import data_bp


CONFIG_PATH = os.path.join(_bundle_dir, "dbase", "bilan_lipidique.json")
PROJECT_ID = "main"
if getattr(sys, 'frozen', False):
    # Packaged: use writable user folder (e.g. %LOCALAPPDATA%\NutriProof\uploads)
    LOCAL_FOLDER = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NutriProof', 'uploads')
else:
    LOCAL_FOLDER = os.path.join('.', 'uploads')

DEMO_MODE = True   # Set to True to limit page count
DEMO_MAX_PAGES = 100
APP_VERSION = '1.1.0'

def create_app():

    # === Initialisation ===
    ocr_document = OCRDocument()
    task_manager = AsyncTaskManager()
    clean_manager = CleanManager()
    
    #Create main project
    local_path = os.path.join(LOCAL_FOLDER, PROJECT_ID)
    os.makedirs(local_path, exist_ok=True)
    # Management des fichiers temporaires
    # clean_manager.clear_folder(LOCAL_FOLDER)
    clean_manager.start()
     
    #Read CONFIG_PATH to get keys order
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    #Get all key values in a list
    key_order = [item.get("label") for item in config if "label" in item]

    # Initialisation de l'application Flask
    app = Flask(__name__,
                template_folder=os.path.join(_bundle_dir, 'templates'),
                static_folder=os.path.join(_bundle_dir, 'static'))
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

    # Store shared objects in app config for blueprints
    app.config['LOCAL_FOLDER'] = LOCAL_FOLDER
    app.config['CONFIG_PATH'] = CONFIG_PATH
    app.config['OCR_DOCUMENT'] = ocr_document
    app.config['TASK_MANAGER'] = task_manager
    app.config['KEY_ORDER'] = key_order

    app.config['DEMO_MODE'] = DEMO_MODE
    app.config['DEMO_MAX_PAGES'] = DEMO_MAX_PAGES

    # Register blueprints
    app.register_blueprint(project_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(ocr_bp)

    @app.context_processor
    def inject_version():
        return {'app_version': APP_VERSION}
    app.register_blueprint(data_bp)


    @app.get("/health")
    def health():
        """Health check endpoint"""
        return {"status": "ok"}

    # Page d'accueil — redirige vers login
    @app.route("/")
    def home():
        return redirect("/login")

    # Page principale (après connexion)
    @app.route("/main")
    def main_page():
        return render_template("index.html")

    # Page de connexion
    @app.route("/login")
    def login():
        return render_template("login.html")

    # Page de révision
    @app.route("/review")
    def review():
        return render_template("review.html")

    
    return app


# Create app instance for gunicorn
app = create_app()

# Start  web server
if __name__ == '__main__':
    # For local development
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}...")
    serve(app, host='0.0.0.0', port=port)
