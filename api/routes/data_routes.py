from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json

from api.firebase_auth import require_auth

data_bp = Blueprint('data', __name__)


# Get image
@data_bp.route("/get_image/<project_id>/<document_id>/<filename>")
@require_auth
def get_image(project_id, document_id, filename):
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    image_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
    if os.path.exists(image_path):
        return send_file(image_path, mimetype="image/png")
    return jsonify("Image not found"), 404


# Get data
@data_bp.route("/get_data/<project_id>/<document_id>/<filename>")
@require_auth
def get_data(project_id, document_id, filename):
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    key_order = current_app.config['KEY_ORDER']

    file_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
    #Create default data dict from key_order labels
    data = {k: "" for k in key_order}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        #match new_data key and copy values in data
        for k in key_order:
            if k in new_data:
                data[k] = new_data[k]
        return jsonify({"data_string": json.dumps(data)})
    return jsonify("File not found"), 404


# Put data
@data_bp.route("/put_data", methods=["POST"])
@require_auth
def put_data():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']

        project_id = request.form.get("project_id")
        document_id = request.form.get("document_id")
        filename = request.form.get("filename")
        data = json.loads(request.form.get("data"))

        if not project_id or not filename or not document_id:
            return jsonify({"error": "Missing project_id or filename or document_id"}), 400

        file_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return jsonify({"message": "File saved", "filename": filename}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Download XLS file
@data_bp.route("/download_xls", methods=["POST"])
@require_auth
def download_xls():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        ocr_document = current_app.config['OCR_DOCUMENT']

        project_id = request.form.get("project_id")
        document_id = request.form.get("document_id")
        nbr_pages = request.form.get("nbr_pages")

        if not project_id or not document_id or not nbr_pages:
            return jsonify({"error": "Missing project_id, document_id or nbr_pages"}), 400

        file_paths = [
            os.path.join(LOCAL_FOLDER, project_id, document_id, f"table_page_{i}.json")
            for i in range(1, int(nbr_pages) + 1)
        ]
        
        xls_file = ocr_document.create_xls_with_data_by_time(file_paths)
        filename = document_id + ".xls"
        return send_file(xls_file, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
