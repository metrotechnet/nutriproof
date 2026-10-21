from flask import Flask, render_template, redirect, send_file
import os, sys, json, io, zipfile
from datetime import datetime
from waitress import serve

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

def _resolve_runtime_log_path():
    env_path = os.environ.get('NUTRIPROOF_LOG_PATH')
    if env_path:
        return env_path

    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
            return os.path.join(base, 'NutriProof', 'debug.log')
        if sys.platform == 'darwin':
            return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'NutriProof', 'debug.log')
        base = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
        return os.path.join(base, 'NutriProof', 'debug.log')

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nutriproof-debug.log')

RUNTIME_LOG_PATH = _resolve_runtime_log_path()


def _write_runtime_log(msg):
    try:
        log_dir = os.path.dirname(RUNTIME_LOG_PATH)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        with open(RUNTIME_LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}] {msg}\n")
            handle.flush()
    except Exception:
        pass


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
    _write_runtime_log(msg)

_pyocr_log(f"[pyocr-fix] app.py loaded; frozen={getattr(sys, 'frozen', False)}; log_path={RUNTIME_LOG_PATH}")

# When running as a PyInstaller bundle, resolve paths relative to the bundle
if getattr(sys, 'frozen', False):
    _bundle_dir = sys._MEIPASS
else:
    _bundle_dir = os.path.dirname(os.path.abspath(__file__))

# Respect a local .env file for local development without requiring manual export.
if load_dotenv is not None:
    _env_path = os.path.join(_bundle_dir, '.env')
    if os.path.exists(_env_path):
        load_dotenv(_env_path)

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

# Ensure the bundled Tesseract binary is discoverable even when pyocr checks
# `shutil.which('tesseract')` before we have modified PATH. The PyInstaller bundle
# keeps the binary next to the backend under ../tesseract-bundle/bin, so inject
# that directory early in the process environment. This must be done BEFORE the
# pyocr module is imported, because pyocr's frozen-mode `_set_environment()` exits
# early when `TESSDATA_PREFIX` is present and otherwise tries the wrong bundled
# path under sys._MEIPASS.
def _ensure_tesseract_in_path():
    bundle_dir = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if os.environ.get('TESSERACT_PATH'):
        candidates.append(os.environ['TESSERACT_PATH'])
    if getattr(sys, 'frozen', False):
        probe = os.path.dirname(bundle_dir)
        for _ in range(4):
            candidates.extend([
                os.path.join(probe, 'tesseract-bundle', 'bin'),
                os.path.join(probe, 'tesseract-bundle'),
                os.path.join(probe, 'tesseract-bundle', 'bin', 'tesseract'),
                os.path.join(probe, 'tesseract-bundle', 'share', 'tessdata'),
            ])
            probe = os.path.dirname(probe)
        candidates.extend([
            os.path.join(bundle_dir, 'tesseract'),
            os.path.join(bundle_dir, 'bin'),
            os.path.join(bundle_dir, 'data', 'tessdata'),
        ])
    for cand in candidates:
        exe = cand if os.path.basename(cand) == 'tesseract' else os.path.join(cand, 'tesseract')
        if os.path.isfile(exe) and os.access(exe, os.X_OK):
            parent = os.path.dirname(exe)
            os.environ['TESSERACT_PATH'] = parent
            os.environ['PATH'] = parent + os.pathsep + os.environ.get('PATH', '')
            tessdata_dir = os.path.join(os.path.dirname(parent), 'share', 'tessdata')
            if not os.path.isdir(tessdata_dir):
                tessdata_dir = os.path.join(os.path.dirname(os.path.dirname(parent)), 'share', 'tessdata')
            if os.path.isdir(tessdata_dir):
                os.environ['TESSDATA_PREFIX'] = tessdata_dir
            if sys.platform == 'darwin':
                for env_key in ('DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH'):
                    lib_dir = os.path.join(os.path.dirname(parent), 'lib')
                    if os.path.isdir(lib_dir):
                        existing = os.environ.get(env_key, '')
                        values = [lib_dir]
                        if existing:
                            values.append(existing)
                        os.environ[env_key] = ':'.join(values)
            _pyocr_log(f"[pyocr-fix] PATH updated with bundled Tesseract: {parent}")
            _pyocr_log(f"[pyocr-fix] TESSDATA_PREFIX={os.environ.get('TESSDATA_PREFIX')}")
            return exe
    _pyocr_log("[pyocr-fix] no bundled tesseract executable found in PATH candidates")
    return None

_tesseract_exe = _ensure_tesseract_in_path()
if _tesseract_exe is not None:
    try:
        import pyocr.tesseract as _pyocr_tesseract
        _pyocr_tesseract.TESSERACT_CMD = _tesseract_exe
        _pyocr_log(f"[pyocr-fix] patched pyocr.tesseract.TESSERACT_CMD={_tesseract_exe}")
        # pyocr's frozen-mode `_set_environment` exits early when `TESSDATA_PREFIX`
        # is already present, otherwise it probes the wrong internal path and fails.
        if 'TESSDATA_PREFIX' in os.environ and hasattr(_pyocr_tesseract, '_set_environment'):
            _pyocr_tesseract._set_environment = lambda: None
            _pyocr_log('[pyocr-fix] patched pyocr.tesseract._set_environment to no-op')
    except Exception as exc:
        _pyocr_log(f"[pyocr-fix] could not patch pyocr.tesseract.TESSERACT_CMD: {exc}")

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
        # argtypes=None means ctypes uses default conversions:
        # - Python int -> c_int (32-bit!) which would TRUNCATE the 64-bit handle pointer.
        # Explicitly wrap pointer args as c_void_p. bytes auto-convert to char*.
        _tr.g_libtesseract.TessBaseAPISetImage(
            _ct.c_void_p(handle),
            imgdata,
            _ct.c_int(image.width),
            _ct.c_int(image.height),
            _ct.c_int(3),
            _ct.c_int(image.width * 3),
        )
        dpi = image.info.get("dpi", [_DPI_DEFAULT])[0]
        _tr.g_libtesseract.TessBaseAPISetSourceResolution(_ct.c_void_p(handle), _ct.c_int(int(dpi)))

    _tr.set_image = _patched_set_image
    _pyocr_log("[pyocr-fix] monkey-patched tesseract_raw.set_image")
except Exception as _e:
    _pyocr_log(f"[pyocr-fix] set_image patch failed: {_e}")

from api.extract_tables import OCRDocument
from api.task_mngr import AsyncTaskManager
from api.clean_mngr import CleanManager
from api.firebase_auth import init_usage_tracker
from api.storage_backend import StorageBackend

from api.routes.project_routes import project_bp
from api.routes.document_routes import document_bp
from api.routes.ocr_routes import ocr_bp
from api.routes.data_routes import data_bp


CONFIG_PATH = os.path.join(_bundle_dir, "dbase", "parameters.json")
PROJECT_ID = "main"
_upload_root_override = os.environ.get('UPLOAD_ROOT')
if _upload_root_override:
    LOCAL_FOLDER = os.path.abspath(_upload_root_override)
elif getattr(sys, 'frozen', False):
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
print(LOCAL_FOLDER)
STORAGE_MODE = os.environ.get("STORAGE_MODE", "local").strip().lower()
GCS_BUCKET = os.environ.get("GCS_BUCKET", "").strip()
GCS_PREFIX = os.environ.get("GCS_PREFIX", "uploads").strip()
_runtime_trace = {
    "platform": sys.platform,
    "frozen": getattr(sys, 'frozen', False),
    "bundle_dir": _bundle_dir,
    "cwd": os.getcwd(),
    "UPLOAD_ROOT": _upload_root_override,
    "LOCAL_FOLDER": LOCAL_FOLDER,
    "STORAGE_MODE": STORAGE_MODE,
    "GCS_BUCKET": GCS_BUCKET or "(unset)",
    "GCS_PREFIX": GCS_PREFIX,
    "CONFIG_PATH": CONFIG_PATH,
}
_pyocr_log("[runtime-trace] startup " + json.dumps(_runtime_trace, ensure_ascii=False))
if STORAGE_MODE == "gcs" and not GCS_BUCKET:
    raise RuntimeError("STORAGE_MODE=gcs requires GCS_BUCKET to be set; local storage is the default and only supported mode.")
DEMO_MODE = False   # Set to True to limit page count
DEMO_MAX_PAGES = 25
APP_VERSION = '1.1.93'

def create_app():

    # === Initialisation ===
    _pyocr_log(f"[runtime-trace] create_app start: platform={sys.platform}, cwd={os.getcwd()}, local_root={LOCAL_FOLDER}")
    ocr_document = OCRDocument()
    task_manager = AsyncTaskManager()
    # clean_manager = CleanManager()
    
    #Create main project
    local_path = os.path.join(LOCAL_FOLDER, PROJECT_ID)
    try:
        os.makedirs(local_path, exist_ok=True)
        _pyocr_log(f"[runtime-trace] ensured project path exists: {local_path}")
    except Exception as exc:
        _pyocr_log(f"[runtime-trace] failed to create project path {local_path}: {exc}")
        raise
    storage_backend = StorageBackend(
        local_root=LOCAL_FOLDER,
        mode=STORAGE_MODE,
        bucket_name=GCS_BUCKET,
        prefix=GCS_PREFIX
    )
    _pyocr_log(f"[runtime-trace] storage_backend initialized: mode={STORAGE_MODE}, local_root={LOCAL_FOLDER}, bucket={GCS_BUCKET or '(unset)'}")
    # Init local usage tracker for demo mode
    init_usage_tracker(LOCAL_FOLDER)
    # Management des fichiers temporaires
    # clean_manager.clear_folder(LOCAL_FOLDER)
    # clean_manager.start()
     
    #Read CONFIG_PATH to get keys order
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    #Build a dict {category: [labels...]} so consumers can pick the right one per document
    key_order = {}
    form_labels = {}
    field_visibility = {}
    field_texts = {}
    field_types = {}
    field_parses = {}
    field_keys = {}
    field_subsections = {}
    field_subsection_by_label = {}

    def _normalize_subsections(raw_subsections):
        out = []
        if not isinstance(raw_subsections, list):
            return out
        for section in raw_subsections:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id", "")).strip()
            if not section_id:
                continue
            label = str(section.get("label", section_id))
            match = section.get("match")
            out.append({
                "id": section_id,
                "label": label,
                "match": match if isinstance(match, dict) else {}
            })
        return out

    def _matches_subsection(item, subsection):
        match = subsection.get("match") or {}
        label = str(item.get("label", ""))
        item_type = str(item.get("type", "information")).strip().lower()

        match_labels = match.get("labels")
        if isinstance(match_labels, list):
            return label in {str(v) for v in match_labels}

        match_prefix = match.get("label_prefix")
        if isinstance(match_prefix, str) and match_prefix:
            return label.startswith(match_prefix)

        match_type = str(match.get("type", "")).strip().lower()
        if match_type:
            return item_type == match_type

        return False

    for category, value in config.items():
        items = value.get("fields", []) if isinstance(value, dict) else value
        if isinstance(items, list):
            sortable_items = []
            for idx, item in enumerate(items):
                order = idx + 1
                if isinstance(item, dict):
                    try:
                        order = int(item.get("order", order))
                    except (TypeError, ValueError):
                        order = idx + 1
                sortable_items.append((order, idx, item))
            sortable_items.sort(key=lambda entry: (entry[0], entry[1]))
            items = [entry[2] for entry in sortable_items]
        subsections = _normalize_subsections(value.get("subsections", [])) if isinstance(value, dict) else []
        key_order[category] = [item.get("label") for item in items if "label" in item]
        field_keys[category] = [str(item.get("key")) for item in items if isinstance(item, dict) and item.get("key") is not None]
        form_labels[category] = value.get("label", category) if isinstance(value, dict) else category
        visibility_by_label = {}
        text_by_label = {}
        type_by_label = {}
        parse_by_label = {}
        subsection_by_label = {}
        for item in items:
            if isinstance(item, dict) and "label" in item:
                visibility_by_label[item["label"]] = bool(item.get("visible", True))
                texts = item.get("text")
                if isinstance(texts, list) and texts:
                    text_by_label[item["label"]] = str(texts[0])
                else:
                    text_by_label[item["label"]] = str(item["label"])
                raw_type = str(item.get("type", "information")).strip().lower()
                type_by_label[item["label"]] = "question" if raw_type == "question" else "information"
                parse_by_label[item["label"]] = item.get("parse")
                for subsection in subsections:
                    if _matches_subsection(item, subsection):
                        subsection_by_label[item["label"]] = subsection["id"]
                        break
        field_visibility[category] = visibility_by_label
        field_texts[category] = text_by_label
        field_types[category] = type_by_label
        field_parses[category] = parse_by_label
        field_subsections[category] = subsections
        field_subsection_by_label[category] = subsection_by_label

    # Initialisation de l'application Flask
    app = Flask(__name__,
                template_folder=os.path.join(_bundle_dir, 'templates'),
                static_folder=os.path.join(_bundle_dir, 'static'))
    _pyocr_log(
        f"[runtime-trace] Flask init: template_dir={app.template_folder}, static_dir={app.static_folder}, "
        f"bundle_dir={_bundle_dir}, platform={sys.platform}"
    )
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

    # Store shared objects in app config for blueprints
    app.config['LOCAL_FOLDER'] = LOCAL_FOLDER
    app.config['CONFIG_PATH'] = CONFIG_PATH
    app.config['OCR_DOCUMENT'] = ocr_document
    app.config['TASK_MANAGER'] = task_manager
    app.config['STORAGE_BACKEND'] = storage_backend
    app.config['KEY_ORDER'] = key_order
    app.config['FORM_LABELS'] = form_labels
    app.config['FIELD_VISIBILITY'] = field_visibility
    app.config['FIELD_TEXTS'] = field_texts
    app.config['FIELD_TYPES'] = field_types
    app.config['FIELD_PARSES'] = field_parses
    app.config['FIELD_KEYS'] = field_keys
    app.config['FIELD_SUBSECTIONS'] = field_subsections
    app.config['FIELD_SUBSECTION_BY_LABEL'] = field_subsection_by_label

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

    @app.get("/export_all")
    def export_all():
        """Download a ZIP archive containing the project data under uploads/main."""
        source_root = os.path.join(app.config.get('LOCAL_FOLDER', LOCAL_FOLDER), 'main')
        if not os.path.isdir(source_root):
            return {"error": f"No exportable data found at {source_root}"}, 404

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            for current_root, _, files in os.walk(source_root):
                for filename in files:
                    full_path = os.path.join(current_root, filename)
                    rel_path = os.path.relpath(full_path, source_root)
                    zip_file.write(full_path, arcname=rel_path)

        zip_buffer.seek(0)
        stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'nutriproof-uploads-{stamp}.zip'
        )

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
_pyocr_log("[runtime-trace] creating Flask app instance")
app = create_app()

# Start  web server
if __name__ == '__main__':
    # For local development
    port = int(os.environ.get('PORT', 8080))
    _pyocr_log(f"[runtime-trace] starting server on port={port}, host=0.0.0.0, platform={sys.platform}")
    print(f"Starting server on port {port}...")
    serve(app, host='0.0.0.0', port=port)
