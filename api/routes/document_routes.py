from flask import Blueprint, request, jsonify, current_app
import os
import uuid
import shutil
from datetime import datetime

from api.routes.helpers import load_project_info, save_project_info
from api.firebase_auth import require_auth

document_bp = Blueprint('document', __name__)


# Suppression d'un document
@document_bp.route('/delete_document', methods=['POST'])
@require_auth
def delete_document():
    project_id = request.form.get('project_id')
    document_id = request.form.get('document_id')
    if not project_id or not document_id:
        return jsonify({'error': 'project_id et document_id requis'}), 400
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        folder_path = os.path.join(LOCAL_FOLDER, project_id, document_id)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Upload PDF
@document_bp.route('/upload_pdf', methods=['POST'])
@require_auth
def upload_pdf():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        ocr_document = current_app.config['OCR_DOCUMENT']

        project_name = request.form.get("projectName")
        if not project_name:
            return jsonify({"error": "Project name is required"}), 400
        
        uploaded_file = request.files.get("file")
        if not uploaded_file:
            return jsonify({"error": "No file uploaded"}), 400

        document_id = uuid.uuid4().hex[:8]

        # Create the project directory on local server
        directory_path = os.path.join(LOCAL_FOLDER, project_name, document_id)
        os.makedirs(directory_path, exist_ok=True)
         
        # Save to local directory
        file_path = os.path.join(directory_path, uploaded_file.filename)
        uploaded_file.save(file_path)
        
        #Get number of pages
        nbrPages = ocr_document.get_pdf_page_count(file_path)
        
        #Set id and nbr page in project_info.json
        project_info = {
            "project_id": project_name,
            "document_id": document_id,
            "filename": uploaded_file.filename,
            "upload_date": datetime.now().isoformat(),
            "nbr_pages": nbrPages,
            "current_page": 0,
            "v1": False,
            "v2": False,
        }
        # save info to file_path
        save_project_info(directory_path, project_info)

        return {
            "message": "ok",
            "document_id": document_id,
            "nbr_pages": nbrPages
        }
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500


# Validation d'un document
@document_bp.route("/validate_document/", methods=["POST"])
@require_auth
def validate_document():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']

        project_name = request.form.get("projectName")
        if not project_name:
            return jsonify({"error": "Project name is required"}), 400

        document_id = request.form.get("documentID")
        if not document_id:
            return jsonify({"error": "Document ID is required"}), 400

        label = request.form.get("label")
        if not label:
            return jsonify({"error": "label is required"}), 400
        
        value = request.form.get("value")
        if not value:
            return jsonify({"error": "value is required"}), 400

        local_path = os.path.join(LOCAL_FOLDER, project_name, document_id)
        project_data = load_project_info(local_path)

        project_data[label] = value

        save_project_info(local_path, project_data)

        return jsonify({"message": "Document validated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
