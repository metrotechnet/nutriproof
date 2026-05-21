from flask import Flask, render_template, redirect
import os, sys, json
from waitress import serve

def _pyocr_log(msg):
    """Write a diagnostic line that survives PyInstaller stderr buffering."""
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    try:
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
    except Exception:
        pass

_pyocr_log(f"[pyocr-fix] app.py loaded; frozen={getattr(sys, 'frozen', False)}")

# When running as a PyInstaller bundle, resolve paths relative to the bundle
if getattr(sys, 'frozen', False):
    _bundle_dir = sys._MEIPASS
else:
    _bundle_dir = os.path.dirname(os.path.abspath(__file__))

# pyocr (frozen mode) checks for tessdata at <_MEIPASS>/data/tessdata (nested!).
# It then sets TESSDATA_PREFIX to <_MEIPASS>/data/tessdata. To make sure pyocr
# finds language files, we ensure that nested folder contains the bundled
# traineddata. This must run BEFORE pyocr is imported.
if getattr(sys, 'frozen', False):
    _pyocr_parent = os.path.join(sys._MEIPASS, 'data')
    _pyocr_data_dir = os.path.join(_pyocr_parent, 'tessdata')
    def _has_traineddata(d):
        try:
            return os.path.isdir(d) and any(
                f.endswith('.traineddata') for f in os.listdir(d)
            )
        except OSError:
            return False
    _has_data = _has_traineddata(_pyocr_data_dir)
    def _list_langs(d):
        try:
            return sorted(f[:-len('.traineddata')] for f in os.listdir(d) if f.endswith('.traineddata'))
        except OSError:
            return []
    _pyocr_log(f"[pyocr-fix] checking {_pyocr_data_dir} has_traineddata={_has_data} langs={_list_langs(_pyocr_data_dir)}")
    if not _has_data:
        _candidates = []
        _tess_env = os.environ.get('TESSDATA_PREFIX')
        if _tess_env:
            _candidates.append(_tess_env)
        _probe = os.path.dirname(sys._MEIPASS)
        for _ in range(4):
            _candidates.append(os.path.join(_probe, 'tesseract-bundle', 'share', 'tessdata'))
            _candidates.append(os.path.join(_probe, 'tesseract-bundle', 'tessdata'))
            _probe = os.path.dirname(_probe)
        _pyocr_log(f"[pyocr-fix] candidates: {_candidates}")
        _src = next((c for c in _candidates if _has_traineddata(c)), None)
        _pyocr_log(f"[pyocr-fix] selected source: {_src}")
        if _src:
            # Make sure the parent <_MEIPASS>/data exists.
            try:
                os.makedirs(_pyocr_parent, exist_ok=True)
            except Exception as e:
                _pyocr_log(f"[pyocr-fix] could not create parent {_pyocr_parent}: {e}")
            # Remove anything stale at the target.
            if os.path.islink(_pyocr_data_dir):
                try:
                    os.unlink(_pyocr_data_dir)
                    _pyocr_log(f"[pyocr-fix] removed stale symlink {_pyocr_data_dir}")
                except Exception as e:
                    _pyocr_log(f"[pyocr-fix] unlink failed: {e}")
            elif os.path.isdir(_pyocr_data_dir):
                try:
                    import shutil
                    shutil.rmtree(_pyocr_data_dir)
                    _pyocr_log(f"[pyocr-fix] removed empty {_pyocr_data_dir}")
                except Exception as e:
                    _pyocr_log(f"[pyocr-fix] rmtree failed: {e}")
            try:
                os.symlink(_src, _pyocr_data_dir)
                _pyocr_log(f"[pyocr-fix] symlinked {_pyocr_data_dir} -> {_src}")
            except (OSError, NotImplementedError) as e:
                _pyocr_log(f"[pyocr-fix] symlink failed: {e}; trying copytree")
                try:
                    import shutil
                    if os.path.exists(_pyocr_data_dir):
                        shutil.rmtree(_pyocr_data_dir, ignore_errors=True)
                    shutil.copytree(_src, _pyocr_data_dir)
                    _pyocr_log(f"[pyocr-fix] copied {_src} -> {_pyocr_data_dir}")
                except Exception as e2:
                    _pyocr_log(f"[pyocr-fix] failed to provision tessdata: {e2}")
        else:
            _pyocr_log("[pyocr-fix] no tesseract-bundle tessdata found in candidates")
        _pyocr_log(
            f"[pyocr-fix] final: {_pyocr_data_dir} has_traineddata={_has_traineddata(_pyocr_data_dir)} langs={_list_langs(_pyocr_data_dir)}"
        )

_pyocr_log("[pyocr-fix] about to import pyocr-using modules")

# pyocr 0.8.5 monkey-patch: on some platforms (notably macOS), ctypes does NOT
# auto-convert a `bytes` object to `POINTER(c_char)`, causing TessBaseAPISetImage
# to raise `argument 2: TypeError: wrong type`. Wrap set_image to pass a proper
# ctypes char array built from the raw image bytes.
try:
    from pyocr.libtesseract import tesseract_raw as _tr
    import ctypes as _ct

    _DPI_DEFAULT = getattr(_tr, "DPI_DEFAULT", 70)

    # Force libtesseract handle to be loaded NOW so we can patch argtypes once
    # (pyocr's init() also rewrites argtypes each time, so we monkey-patch the
    # init function as well to re-apply our relaxed argtypes after it runs).
    try:
        _tr.init(lang=None)
        _pyocr_log("[pyocr-fix] tesseract_raw.init() succeeded")
    except Exception as _ie:
        _pyocr_log(f"[pyocr-fix] tesseract_raw.init() raised: {_ie}")

    def _relax_argtypes():
        try:
            lib = _tr.g_libtesseract
            if lib is None:
                return False
            # Disable argtype checking entirely (sledgehammer): ctypes will
            # then use default conversions and bytes -> char* works on all
            # platforms.
            lib.TessBaseAPISetImage.argtypes = None
            lib.TessBaseAPISetImage.restype = None
            return True
        except Exception as e:
            _pyocr_log(f"[pyocr-fix] _relax_argtypes failed: {e}")
            return False

    _ok = _relax_argtypes()
    _pyocr_log(f"[pyocr-fix] relaxed argtypes ok={_ok}")
    try:
        _pyocr_log(
            f"[pyocr-fix] argtypes after relax: {_tr.g_libtesseract.TessBaseAPISetImage.argtypes}"
        )
    except Exception as _ee:
        _pyocr_log(f"[pyocr-fix] read-back argtypes failed: {_ee}")

    # Wrap init so any subsequent call re-applies our relaxed argtypes.
    _orig_init = _tr.init
    def _patched_init(lang=None):
        r = _orig_init(lang)
        _relax_argtypes()
        return r
    _tr.init = _patched_init

    def _patched_set_image(handle, image):
        assert _tr.g_libtesseract is not None
        image = image.convert("RGB")
        image.load()
        imgdata = image.tobytes("raw", "RGB")
        _relax_argtypes()  # belt-and-suspenders
        # With argtypes=None, pass plain Python values; ctypes default
        # conversion translates bytes -> char* and ints -> c_int.
        _tr.g_libtesseract.TessBaseAPISetImage(
            handle,
            imgdata,
            image.width,
            image.height,
            3,
            image.width * 3,
        )
        dpi = image.info.get("dpi", [_DPI_DEFAULT])[0]
        _tr.g_libtesseract.TessBaseAPISetSourceResolution(handle, dpi)

    _tr.set_image = _patched_set_image
    _pyocr_log("[pyocr-fix] monkey-patched tesseract_raw.set_image")
except Exception as _e:
    _pyocr_log(f"[pyocr-fix] set_image patch failed: {_e}")

from api.extract_tables import OCRDocument
from api.task_mngr import AsyncTaskManager
from api.clean_mngr import CleanManager
from api.firebase_auth import init_usage_tracker

from api.routes.project_routes import project_bp
from api.routes.document_routes import document_bp
from api.routes.ocr_routes import ocr_bp
from api.routes.data_routes import data_bp


CONFIG_PATH = os.path.join(_bundle_dir, "dbase", "bilan_lipidique.json")
PROJECT_ID = "main"
if getattr(sys, 'frozen', False):
    # Packaged: use platform-appropriate writable user data folder.
    if sys.platform == 'win32':
        # Windows: %LOCALAPPDATA%\NutriProof\uploads
        _base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        LOCAL_FOLDER = os.path.join(_base, 'NutriProof', 'uploads')
    elif sys.platform == 'darwin':
        # macOS: ~/Library/Application Support/NutriProof/uploads
        LOCAL_FOLDER = os.path.join(
            os.path.expanduser('~'), 'Library', 'Application Support', 'NutriProof', 'uploads'
        )
    else:
        # Linux/other: $XDG_DATA_HOME/NutriProof/uploads or ~/.local/share/NutriProof/uploads
        _base = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
        LOCAL_FOLDER = os.path.join(_base, 'NutriProof', 'uploads')
else:
    LOCAL_FOLDER = os.path.join('.', 'uploads')

DEMO_MODE = False   # Set to True to limit page count
DEMO_MAX_PAGES = 25
APP_VERSION = '1.1.39'

def create_app():

    # === Initialisation ===
    ocr_document = OCRDocument()
    task_manager = AsyncTaskManager()
    # clean_manager = CleanManager()
    
    #Create main project
    local_path = os.path.join(LOCAL_FOLDER, PROJECT_ID)
    os.makedirs(local_path, exist_ok=True)
    # Init local usage tracker for demo mode
    init_usage_tracker(LOCAL_FOLDER)
    # Management des fichiers temporaires
    # clean_manager.clear_folder(LOCAL_FOLDER)
    # clean_manager.start()
     
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

    # Page d'accueil
    @app.route("/")
    def home():
        return redirect("/main")

    # Page principale
    @app.route("/main")
    def main_page():
        return render_template("index.html")

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
