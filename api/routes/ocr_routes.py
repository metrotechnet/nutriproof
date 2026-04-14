from flask import Blueprint, request, jsonify, current_app
import os
import json

from api.routes.helpers import load_project_info, save_project_info

ocr_bp = Blueprint('ocr', __name__)


# Process OCR
@ocr_bp.route("/process_ocr", methods=["POST"])
def process_ocr():
    try:
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        CONFIG_PATH = current_app.config['CONFIG_PATH']
        ocr_document = current_app.config['OCR_DOCUMENT']
        task_manager = current_app.config['TASK_MANAGER']

        project_name = request.form.get("projectName")
        if not project_name:
            return jsonify({"error": "Project name is required"}), 400

        document_id = request.form.get("documentID")
        if not document_id:
            return jsonify({"error": "Document ID is required"}), 400

        filename = request.form.get("fileName")
        if not filename:
            return jsonify({"error": "Filename is required"}), 400

        nbr_pages = request.form.get("nbrPages")
        if not nbr_pages:
            return jsonify({"error": "Number of pages is required"}), 400
        nbr_pages = int(nbr_pages)
        
        start_page = request.form.get("startPage")
        if not start_page:
            return jsonify({"error": "Start page is required"}), 400
        start_page = int(start_page)
        
        async def run_extraction(job_id):
            try:
                local_path = f'{LOCAL_FOLDER}/{project_name}/{document_id}/'
                os.makedirs(local_path, exist_ok=True)
                for idx in range(start_page, nbr_pages):
                    # Check if the task is cancelled
                    if task_manager.is_cancelled(job_id):
                        return jsonify("Job Canceled"), 404
                    
                    # extract page from pdf
                    chunk_file = ocr_document.get_pdf_image(local_path+filename, local_path, page_index=idx, dpi=300)
                    
                    # Set progress
                    progress = f"{idx + 1}/{nbr_pages} pages"
                    task_manager.set_progress(job_id, progress)
                    
                    # Get page ID
                    pageid = os.path.splitext(os.path.basename(chunk_file))[0]
                    
                    # Get document layout
                    layout = ocr_document.get_document_layout(chunk_file, mime_type="image/png")
                    
                    # Save layout to JSON
                    layout_json_path = os.path.join(local_path, f"output_{pageid}.json")
                    with open(layout_json_path, "w", encoding="utf-8") as f:
                        json.dump(layout, f, indent=4, ensure_ascii=False)

                    # Extract tables
                    ocr_document.extract_tables(CONFIG_PATH, layout_json_path, local_path, pageid)

                    # Save page index in project info
                    project_data = load_project_info(local_path)
                    project_data['current_page'] = idx + 1
                    save_project_info(local_path, project_data)

                return {
                    "nbr_pages": nbr_pages
                }

            except Exception as e:
                return {"error": str(e)}

        return task_manager.run_task(document_id, run_extraction)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Get the status of a job
@ocr_bp.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    try:
        task_manager = current_app.config['TASK_MANAGER']
        return task_manager.check_status(job_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Cancel a job
@ocr_bp.route("/cancel/<job_id>", methods=["GET"])
def cancel(job_id):
    try:
        task_manager = current_app.config['TASK_MANAGER']
        return task_manager.cancel_task(job_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
