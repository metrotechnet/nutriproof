from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json
import re

from api.routes.helpers import load_project_info

data_bp = Blueprint('data', __name__)

TABLE_PAGE_RE = re.compile(r"^table_(page_\d+)\.json$", re.IGNORECASE)


@data_bp.route("/get_form_types")
def get_form_types():
    """Return a dict {category_key: display_label} for all configured form types."""
    form_labels = current_app.config.get('FORM_LABELS', {})
    return jsonify(form_labels)


def _resolve_key_order(project_id, document_id):
    """Return the label list for the document's category.

    Resolution order:
      1. ?category=... query param (explicit override)
      2. 'category' field in the document's info.json
      3. First category defined in parameters.json (fallback)
    """
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    storage_backend = current_app.config['STORAGE_BACKEND']
    key_order_map = current_app.config['KEY_ORDER']  # {category: [labels]}

    category = request.args.get('category')
    if not category:
        try:
            storage_backend.hydrate_document(project_id, document_id)
            info = load_project_info(os.path.join(LOCAL_FOLDER, project_id, document_id))
            category = info.get('category')
        except Exception:
            category = None

    if category and category in key_order_map:
        return key_order_map[category], category

    # Fallback: first category in the config
    first_cat = next(iter(key_order_map))
    return key_order_map[first_cat], first_cat


def _page_id_from_data_filename(filename):
    m = re.match(r'^(?:label_bbox|value_bbox|table)_(page_\d+)\.json$', filename or "")
    return m.group(1) if m else None


def _table_paths_for_page(document_dir, page_id):
    legacy_path = os.path.join(document_dir, f"table_{page_id}.json")
    return {
        "legacy": legacy_path,
        "ocr": os.path.join(document_dir, f"table_ocr_{page_id}.json"),
    }


def _resolve_table_read_path(document_dir, page_id, source="edited"):
    paths = _table_paths_for_page(document_dir, page_id)
    source_mode = str(source or "edited").strip().lower()
    if source_mode == "raw":
        if os.path.exists(paths["ocr"]):
            return paths["ocr"]
        if os.path.exists(paths["legacy"]):
            return paths["legacy"]
        return paths["ocr"]
    return paths["legacy"]


def _resolve_table_write_path(document_dir, filename):
    m = TABLE_PAGE_RE.match(filename or "")
    if not m:
        return os.path.join(document_dir, filename), filename
    page_id = m.group(1)
    edited_name = f"table_{page_id}.json"
    return os.path.join(document_dir, edited_name), edited_name


def _read_matched_group(LOCAL_FOLDER, project_id, document_id, filename):
    """Read matched group id (1/2/3) from the page table JSON if available."""
    page_id = _page_id_from_data_filename(filename)
    if not page_id:
        return None

    document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
    table_path = _resolve_table_read_path(document_dir, page_id, source="edited")
    if not os.path.exists(table_path):
        return None

    try:
        with open(table_path, 'r', encoding='utf-8') as f:
            table_data = json.load(f)
    except Exception:
        return None

    if not isinstance(table_data, dict):
        return None

    raw_group = table_data.get("Intervention nutritionnelle") or table_data.get("Groupe de randomisation")
    if isinstance(raw_group, (int, float)):
        raw_group = str(int(raw_group))
    if not isinstance(raw_group, str):
        return None

    s = raw_group.strip().upper()
    m = re.match(r'^G?\s*([123])$', s)
    return m.group(1) if m else None


def _read_field_text_overrides(LOCAL_FOLDER, project_id, document_id, filename):
    """Read per-page matched question text overrides (label -> best matched text)."""
    page_id = _page_id_from_data_filename(filename)
    if not page_id:
        return {}
    path = os.path.join(LOCAL_FOLDER, project_id, document_id, f"field_text_{page_id}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _filter_labels_by_group(labels, matched_group):
    """Keep common labels and only the labels for the selected intervention group."""
    if not matched_group:
        return labels

    group_num = str(matched_group).strip()
    group_label_map = {
        "1": {
            "respect proportion gac",
            "privilégié grains entiers",
            "protéines végétales",
            "privilégié l'eau",
            "% protéines r24w",
            "% lipides r24w",
            "% glucides r24w",
            "act. physique",
            "sommeil",
        },
        "2": {
            "protéines à chaque repas",
            "fruits et légumes",
            "gras insaturés",
            "produits laitiers",
            "faible ig",
            "capsaïcine",
            "privilégie aliments rassasiants",
            "privilégié grains entiers",
            "privilégié l'eau",
            "% protéines r24w",
            "% lipides r24w",
            "% glucides r24w",
            "fibres r24w",
            "calcium r24w",
            "act. physique",
            "sommeil",
        },
        "3": {
            "nbr portions féculents",
            "nbr portions viandes",
            "nbr portions fruits et sucres",
            "nbr portions légumes",
            "nbr portions lait",
            "nbr portions mg",
            "déficit 500 cal/jour r24w",
            "% protéines r24w",
            "% lipides r24w",
            "% glucides r24w",
            "act. physique",
            "sommeil",
        },
    }
    selected = group_label_map.get(group_num)
    if not selected:
        return labels

    def _norm(s):
        return (s or "").strip().lower()

    grouped_union = set().union(*group_label_map.values())
    out = []
    for label in labels:
        if not isinstance(label, str):
            continue
        nl = _norm(label)
        if nl not in grouped_union:
            out.append(label)  # common/non-group labels
            continue
        if nl in selected:
            out.append(label)
    return out


# Get image
@data_bp.route("/get_image/<project_id>/<document_id>/<filename>")
def get_image(project_id, document_id, filename):
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    storage_backend = current_app.config['STORAGE_BACKEND']
    image_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
    if not os.path.exists(image_path) and storage_backend.mode == "gcs":
        storage_backend.hydrate_document(project_id, document_id)
    if os.path.exists(image_path):
        return send_file(image_path, mimetype="image/png")
    return jsonify("Image not found"), 404


# Get data
@data_bp.route("/get_data/<project_id>/<document_id>/<filename>")
def get_data(project_id, document_id, filename):
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    storage_backend = current_app.config['STORAGE_BACKEND']
    document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
    if (not os.path.exists(document_dir) or not os.path.exists(os.path.join(document_dir, "info.json"))) and storage_backend.mode == "gcs":
        storage_backend.hydrate_document(project_id, document_id)
    key_order, category = _resolve_key_order(project_id, document_id)
    matched_group = _read_matched_group(LOCAL_FOLDER, project_id, document_id, filename)
    key_order = _filter_labels_by_group(key_order, matched_group)
    all_visibility = current_app.config.get('FIELD_VISIBILITY', {})
    category_visibility = all_visibility.get(category, {})
    field_visibility = {label: bool(category_visibility.get(label, True)) for label in key_order}
    all_texts = current_app.config.get('FIELD_TEXTS', {})
    category_texts = all_texts.get(category, {})
    field_text = {label: str(category_texts.get(label, label)) for label in key_order}
    page_text_overrides = _read_field_text_overrides(LOCAL_FOLDER, project_id, document_id, filename)
    for label in key_order:
        override_text = page_text_overrides.get(label)
        if isinstance(override_text, str) and override_text.strip():
            field_text[label] = override_text
    all_types = current_app.config.get('FIELD_TYPES', {})
    category_types = all_types.get(category, {})
    field_type = {label: str(category_types.get(label, "information")) for label in key_order}
    all_parses = current_app.config.get('FIELD_PARSES', {})
    category_parses = all_parses.get(category, {})
    field_parse = {label: category_parses.get(label) for label in key_order}
    all_subsections = current_app.config.get('FIELD_SUBSECTIONS', {})
    category_subsections = all_subsections.get(category, [])
    all_subsection_by_label = current_app.config.get('FIELD_SUBSECTION_BY_LABEL', {})
    category_subsection_by_label = all_subsection_by_label.get(category, {})
    field_subsection = {label: category_subsection_by_label.get(label) for label in key_order}

    page_id = _page_id_from_data_filename(filename)
    source = request.args.get("source", "edited")
    if page_id and filename.startswith("table_"):
        file_path = _resolve_table_read_path(document_dir, page_id, source=source)
    else:
        file_path = os.path.join(document_dir, filename)
    data = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        if isinstance(new_data, dict):
            # Keep only keys that are actually present in the saved page payload.
            # Do not synthesize or append configured keys that are absent from the
            # file itself, otherwise the review UI receives extra empty values.
            allowed = set(key_order)
            allowed.update(current_app.config.get('FIELD_KEYS', {}).get(category, []))
            allowed.update({"No du participant", "Date d'observation (DD-MM-YY)", "nomat", "date_visite"})
            data = {k: new_data[k] for k in new_data.keys() if k in allowed}
        else:
            # Fallback for unexpected non-dict payloads.
            data = {}
        return jsonify({
            "data_string": json.dumps(data),
            "category": category,
            "field_order": key_order,
            "field_visibility": field_visibility,
            "field_text": field_text,
            "field_type": field_type,
            "field_parse": field_parse,
            "field_subsection": field_subsection,
            "subsections": category_subsections
        })
    return jsonify("File not found"), 404


# Get raw JSON file
@data_bp.route("/get_raw_data/<project_id>/<document_id>/<filename>")
def get_raw_data(project_id, document_id, filename):
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    storage_backend = current_app.config['STORAGE_BACKEND']
    storage_backend.hydrate_document(project_id, document_id)
    file_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify([]), 200


# Put data
@data_bp.route("/put_data", methods=["POST"])
def put_data():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        storage_backend = current_app.config['STORAGE_BACKEND']

        project_id = request.form.get("project_id")
        document_id = request.form.get("document_id")
        filename = request.form.get("filename")
        data = json.loads(request.form.get("data"))

        if not project_id or not filename or not document_id:
            return jsonify({"error": "Missing project_id or filename or document_id"}), 400

        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        storage_backend.hydrate_document(project_id, document_id)
        
        file_path, saved_filename = _resolve_table_write_path(document_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return jsonify({"message": "File saved", "filename": saved_filename}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _collect_document_file_paths(document_dir, nbr_pages):
    file_paths = []
    for i in range(1, int(nbr_pages) + 1):
        page_id = f"page_{i}"
        file_paths.append(_resolve_table_read_path(document_dir, page_id, source="edited"))
    return file_paths


def _load_sample_data(file_paths):
    for path in file_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}


FORMULAIRE_SUIVI_KEYS = {
    "Projet", "Section", "Centre", "nomat", "seq", "tx", "Visites", "date_visite",
    "mode_renc", "weight_lbs", "weight_kg", "poids_m", "waistc", "jb_remis",
    "fq_comp", "date_rappel", "group_rando", "prop_gac", "grains_entiers",
    "prot_veg", "priv_eau", "prot_r24", "lip_r24", "gluc_r24", "act_phys",
    "sommeil", "prot_repas", "fruit_leg", "gras_insat", "prod_lait", "faib_ig",
    "capsa", "alim_rassa", "fibr_r24", "calci_r24", "port_fecul", "port_viand",
    "fruit_sucr", "port_leg", "port_laits", "port_mg", "def_cal"
}


def _normalize_key_name(key):
    return re.sub(r"[^a-z0-9]+", "", str(key).lower())


def _is_formulaire_suivi_data(sample_data):
    if not sample_data:
        return False

    normalized_form_keys = {_normalize_key_name(key) for key in FORMULAIRE_SUIVI_KEYS}
    sample_keys = {str(k).lower() for k in sample_data.keys()}
    normalized_sample_keys = {_normalize_key_name(k) for k in sample_data.keys()}

    return (
        any(key in sample_data for key in FORMULAIRE_SUIVI_KEYS)
        or any(str(k).lower() in {key.lower() for key in FORMULAIRE_SUIVI_KEYS} for k in sample_data.keys())
        or bool(normalized_sample_keys & normalized_form_keys)
    )


def _build_xls_for_document(ocr_document, file_paths, sample_data=None, force_form=None):
    if force_form == "formulaire_suivi":
        return ocr_document.create_xls_with_data_formulaire_suivi(file_paths)

    if sample_data is None:
        sample_data = _load_sample_data(file_paths)

    if _is_formulaire_suivi_data(sample_data):
        return ocr_document.create_xls_with_data_formulaire_suivi(file_paths)
    return ocr_document.create_xls_with_data_by_time(file_paths)


# Download XLS file
@data_bp.route("/download_xls", methods=["POST"])
def download_xls():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        ocr_document = current_app.config['OCR_DOCUMENT']
        storage_backend = current_app.config['STORAGE_BACKEND']

        project_id = request.form.get("project_id")
        document_id = request.form.get("document_id")
        nbr_pages = request.form.get("nbr_pages")

        if not project_id or not document_id or not nbr_pages:
            return jsonify({"error": "Missing project_id, document_id or nbr_pages"}), 400

        storage_backend.hydrate_document(project_id, document_id)
        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        file_paths = _collect_document_file_paths(document_dir, nbr_pages)
        sample_data = _load_sample_data(file_paths)
        xls_file = _build_xls_for_document(ocr_document, file_paths, sample_data=sample_data)

        filename = document_id + ".xls"
        return send_file(xls_file, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@data_bp.route("/download_xls_formulaire_suivi", methods=["POST"])
def download_xls_formulaire_suivi():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        ocr_document = current_app.config['OCR_DOCUMENT']
        storage_backend = current_app.config['STORAGE_BACKEND']

        project_id = request.form.get("project_id")
        document_id = request.form.get("document_id")
        nbr_pages = request.form.get("nbr_pages")

        if not project_id or not document_id or not nbr_pages:
            return jsonify({"error": "Missing project_id, document_id or nbr_pages"}), 400

        storage_backend.hydrate_document(project_id, document_id)
        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        file_paths = _collect_document_file_paths(document_dir, nbr_pages)
        xls_file = _build_xls_for_document(
            ocr_document,
            file_paths,
            sample_data=_load_sample_data(file_paths),
            force_form="formulaire_suivi",
        )

        filename = document_id + "_formulaire_suivi.xls"
        return send_file(xls_file, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@data_bp.route("/export_all", methods=["POST"])
def export_all_xls():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        ocr_document = current_app.config['OCR_DOCUMENT']
        storage_backend = current_app.config['STORAGE_BACKEND']

        payload = request.get_json(silent=True) or {}
        project_id = payload.get("project_id")
        documents = payload.get("documents")

        if not project_id or not isinstance(documents, list) or not documents:
            return jsonify({"error": "Missing project_id or documents payload"}), 400

        all_file_paths = []
        discovered_categories = set()

        for item in documents:
            if not isinstance(item, dict):
                return jsonify({"error": "Invalid document entry in payload"}), 400

            document_id = item.get("document_id")
            nbr_pages = item.get("nbr_pages")
            if not document_id or not nbr_pages:
                return jsonify({"error": "Each document must include document_id and nbr_pages"}), 400

            storage_backend.hydrate_document(project_id, document_id)
            document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)

            info = load_project_info(document_dir)
            category = str(info.get("category") or "").strip()
            if category:
                discovered_categories.add(category)

            all_file_paths.extend(_collect_document_file_paths(document_dir, nbr_pages))

        if not all_file_paths:
            return jsonify({"error": "No data files found for selected documents"}), 400

        if len(discovered_categories) > 1:
            return jsonify({"error": "All selected documents must have the same type"}), 400

        selected_category = str(payload.get("category") or "").strip()
        if discovered_categories:
            selected_category = next(iter(discovered_categories))

        force_form = "formulaire_suivi" if selected_category == "formulaire_suivi" else None
        xls_file = _build_xls_for_document(
            ocr_document,
            all_file_paths,
            sample_data=_load_sample_data(all_file_paths),
            force_form=force_form,
        )

        filename = f"{project_id}_export_all.xls"
        return send_file(xls_file, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
