from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json
import re
from datetime import datetime, timezone
import uuid

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
    key_order_map = current_app.config['KEY_ORDER']  # {category: [labels]}

    category = request.args.get('category')
    if not category:
        try:
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
    return {
        "legacy": os.path.join(document_dir, f"table_{page_id}.json"),
        "ocr": os.path.join(document_dir, f"table_ocr_{page_id}.json"),
        "edited": os.path.join(document_dir, f"table_edited_{page_id}.json"),
    }


def _data_links_path(document_dir):
    return os.path.join(document_dir, "table_data_links.json")


def _load_data_links(document_dir):
    path = _data_links_path(document_dir)
    default_obj = {"active_data_id": None, "page_data_ids": {}, "datasets": {}}
    if not os.path.exists(path):
        return default_obj
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if not isinstance(obj, dict):
            return default_obj
        return {
            "active_data_id": obj.get("active_data_id"),
            "page_data_ids": obj.get("page_data_ids") if isinstance(obj.get("page_data_ids"), dict) else {},
            "datasets": obj.get("datasets") if isinstance(obj.get("datasets"), dict) else {},
        }
    except Exception:
        return default_obj


def _save_data_links(document_dir, links):
    path = _data_links_path(document_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(links, f, indent=2, ensure_ascii=False)


def _dataset_filename(data_id):
    return f"table_data_{data_id}.json"


def _new_data_id():
    return uuid.uuid4().hex[:12]


def _resolve_linked_table_path(document_dir, page_id):
    links = _load_data_links(document_dir)
    page_data_ids = links.get("page_data_ids", {})
    datasets = links.get("datasets", {})
    data_id = page_data_ids.get(page_id)
    if not data_id:
        return None, links
    meta = datasets.get(data_id, {})
    filename = meta.get("filename") if isinstance(meta, dict) else None
    if not filename:
        filename = _dataset_filename(data_id)
    return os.path.join(document_dir, filename), links


def _read_raw_table_for_page(document_dir, page_id):
    path = _resolve_table_read_path(document_dir, page_id, source="raw")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
    return {}


def _resolve_table_read_path(document_dir, page_id, source="auto"):
    if str(source or "").strip().lower() == "linked":
        linked_path, _ = _resolve_linked_table_path(document_dir, page_id)
        return linked_path or ""

    paths = _table_paths_for_page(document_dir, page_id)
    source_mode = str(source or "auto").strip().lower()
    if source_mode == "raw":
        if os.path.exists(paths["ocr"]):
            return paths["ocr"]
        if os.path.exists(paths["legacy"]):
            return paths["legacy"]
        return paths["ocr"]
    if source_mode == "edited":
        if os.path.exists(paths["edited"]):
            return paths["edited"]
        return paths["edited"]
    # auto
    if os.path.exists(paths["edited"]):
        return paths["edited"]
    if os.path.exists(paths["legacy"]):
        return paths["legacy"]
    return paths["ocr"]


def _resolve_table_write_path(document_dir, filename):
    m = TABLE_PAGE_RE.match(filename or "")
    if not m:
        return os.path.join(document_dir, filename), filename
    page_id = m.group(1)
    linked_path, links = _resolve_linked_table_path(document_dir, page_id)
    if linked_path:
        return linked_path, os.path.basename(linked_path)
    edited_name = f"table_edited_{page_id}.json"
    return os.path.join(document_dir, edited_name), edited_name


def _read_matched_group(LOCAL_FOLDER, project_id, document_id, filename):
    """Read matched group id (1/2/3) from the page table JSON if available."""
    page_id = _page_id_from_data_filename(filename)
    if not page_id:
        return None

    document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
    table_path = _resolve_table_read_path(document_dir, page_id, source="auto")
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
    image_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
    if os.path.exists(image_path):
        return send_file(image_path, mimetype="image/png")
    return jsonify("Image not found"), 404


# Get data
@data_bp.route("/get_data/<project_id>/<document_id>/<filename>")
def get_data(project_id, document_id, filename):
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
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
    all_subsections = current_app.config.get('FIELD_SUBSECTIONS', {})
    category_subsections = all_subsections.get(category, [])
    all_subsection_by_label = current_app.config.get('FIELD_SUBSECTION_BY_LABEL', {})
    category_subsection_by_label = all_subsection_by_label.get(category, {})
    field_subsection = {label: category_subsection_by_label.get(label) for label in key_order}

    page_id = _page_id_from_data_filename(filename)
    source = request.args.get("source", "auto")
    links = _load_data_links(document_dir)
    if page_id and filename.startswith("table_"):
        file_path = _resolve_table_read_path(document_dir, page_id, source=source)
    else:
        file_path = os.path.join(document_dir, filename)
    #Create default data dict from key_order labels
    data = {k: "" for k in key_order}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        # Preserve file key order first (when JSON was preordered upstream),
        # then append any remaining configured keys.
        if isinstance(new_data, dict):
            allowed = set(key_order)
            ordered_keys = []
            for k in new_data.keys():
                if k in allowed:
                    ordered_keys.append(k)
            for k in key_order:
                if k not in ordered_keys:
                    ordered_keys.append(k)
            data = {k: new_data.get(k, "") for k in ordered_keys}
        else:
            # Fallback for unexpected non-dict payloads.
            for k in key_order:
                if k in new_data:
                    data[k] = new_data[k]
        return jsonify({
            "data_string": json.dumps(data),
            "category": category,
            "field_visibility": field_visibility,
            "field_text": field_text,
            "field_type": field_type,
            "field_subsection": field_subsection,
            "subsections": category_subsections,
            "active_data_id": links.get("active_data_id"),
            "page_data_id": links.get("page_data_ids", {}).get(page_id) if page_id else None
        })
    if page_id and filename.startswith("table_") and str(source).strip().lower() == "linked":
        # Strict linked mode: if page has no linked edited dataset yet, return an empty table shape.
        return jsonify({
            "data_string": json.dumps(data),
            "category": category,
            "field_visibility": field_visibility,
            "field_text": field_text,
            "field_type": field_type,
            "field_subsection": field_subsection,
            "subsections": category_subsections,
            "active_data_id": links.get("active_data_id"),
            "page_data_id": links.get("page_data_ids", {}).get(page_id) if page_id else None
        })
    return jsonify("File not found"), 404


# Get raw JSON file
@data_bp.route("/get_raw_data/<project_id>/<document_id>/<filename>")
def get_raw_data(project_id, document_id, filename):
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
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

        project_id = request.form.get("project_id")
        document_id = request.form.get("document_id")
        filename = request.form.get("filename")
        data = json.loads(request.form.get("data"))

        if not project_id or not filename or not document_id:
            return jsonify({"error": "Missing project_id or filename or document_id"}), 400

        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        file_path, saved_filename = _resolve_table_write_path(document_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return jsonify({"message": "File saved", "filename": saved_filename}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_bp.route("/new_data_version", methods=["POST"])
def new_data_version():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        payload = request.get_json(silent=True) or {}
        project_id = payload.get("project_id")
        document_id = payload.get("document_id")
        page_id = payload.get("page_id")
        if not project_id or not document_id or not page_id:
            return jsonify({"error": "Missing project_id or document_id or page_id"}), 400

        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        os.makedirs(document_dir, exist_ok=True)
        raw_data = _read_raw_table_for_page(document_dir, page_id)

        data_id = _new_data_id()
        data_filename = _dataset_filename(data_id)
        data_path = os.path.join(document_dir, data_filename)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)

        links = _load_data_links(document_dir)
        links["active_data_id"] = data_id
        page_data_ids = links.get("page_data_ids", {})
        datasets = links.get("datasets", {})
        page_data_ids[page_id] = data_id
        datasets[data_id] = {
            "filename": data_filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seed_source": "raw",
            "seed_page": page_id,
        }
        links["page_data_ids"] = page_data_ids
        links["datasets"] = datasets
        _save_data_links(document_dir, links)

        return jsonify({
            "message": "New data version created",
            "data_id": data_id,
            "page_id": page_id,
            "filename": data_filename
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_bp.route("/get_active_data/<project_id>/<document_id>")
def get_active_data(project_id, document_id):
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        links = _load_data_links(document_dir)
        return jsonify({
            "active_data_id": links.get("active_data_id"),
            "page_data_ids": links.get("page_data_ids", {})
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_bp.route("/link_active_data_to_page", methods=["POST"])
def link_active_data_to_page():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        payload = request.get_json(silent=True) or {}
        project_id = payload.get("project_id")
        document_id = payload.get("document_id")
        page_id = payload.get("page_id")
        if not project_id or not document_id or not page_id:
            return jsonify({"error": "Missing project_id or document_id or page_id"}), 400

        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        links = _load_data_links(document_dir)
        active_data_id = links.get("active_data_id")
        if not active_data_id:
            return jsonify({"error": "No active data id set"}), 400

        datasets = links.get("datasets", {})
        meta = datasets.get(active_data_id, {})
        filename = meta.get("filename") if isinstance(meta, dict) else _dataset_filename(active_data_id)
        if not filename:
            filename = _dataset_filename(active_data_id)
        data_path = os.path.join(document_dir, filename)
        if not os.path.exists(data_path):
            return jsonify({"error": f"Active data file not found: {filename}"}), 404

        page_data_ids = links.get("page_data_ids", {})
        page_data_ids[page_id] = active_data_id
        links["page_data_ids"] = page_data_ids
        _save_data_links(document_dir, links)

        return jsonify({
            "message": "Active data linked to page",
            "data_id": active_data_id,
            "page_id": page_id
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Download XLS file
@data_bp.route("/download_xls", methods=["POST"])
def download_xls():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        ocr_document = current_app.config['OCR_DOCUMENT']

        project_id = request.form.get("project_id")
        document_id = request.form.get("document_id")
        nbr_pages = request.form.get("nbr_pages")

        if not project_id or not document_id or not nbr_pages:
            return jsonify({"error": "Missing project_id, document_id or nbr_pages"}), 400

        document_dir = os.path.join(LOCAL_FOLDER, project_id, document_id)
        file_paths = []
        for i in range(1, int(nbr_pages) + 1):
            page_id = f"page_{i}"
            file_paths.append(_resolve_table_read_path(document_dir, page_id, source="auto"))
        
        xls_file = ocr_document.create_xls_with_data_by_time(file_paths)
        filename = document_id + ".xls"
        return send_file(xls_file, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
