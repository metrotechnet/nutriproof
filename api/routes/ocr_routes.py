from PIL import Image
from flask import Blueprint, request, jsonify, current_app
import os
import sys
import json

from api.routes.helpers import load_project_info, save_project_info

ocr_bp = Blueprint('ocr', __name__)

from api.grid_detector import GridDetector
grid_detector = GridDetector()

def _trace(msg):
    line = f"[ocr-route] {msg}"
    try:
        sys.stderr.write(line + "\n"); sys.stderr.flush()
    except Exception:
        pass



# Process OCR
@ocr_bp.route("/process_ocr", methods=["POST"])
def process_ocr():
    _trace("process_ocr: route hit")
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

        # Form type chosen by the user. Fallback to info.json if missing.
        category = request.form.get("category")
        if not category:
            try:
                info = load_project_info(os.path.join(LOCAL_FOLDER, project_name, document_id))
                category = info.get('category')
            except Exception:
                category = None
        allowed_categories = list(current_app.config.get('KEY_ORDER', {}).keys())
        if not category or category not in allowed_categories:
            return jsonify({"error": f"Invalid or missing category. Expected one of: {allowed_categories}"}), 400
        
        async def run_extraction(job_id):
            _trace(f"run_extraction: start job_id={job_id} doc={document_id} pages={start_page}..{nbr_pages}")
            try:
                local_path = f'{LOCAL_FOLDER}/{project_name}/{document_id}/'
                os.makedirs(local_path, exist_ok=True)
                _trace(f"run_extraction: local_path={local_path}")
                for idx in range(start_page, nbr_pages):
                    _trace(f"run_extraction: page idx={idx}")
                    # Check if the task is cancelled
                    if task_manager.is_cancelled(job_id):
                        _trace(f"run_extraction: cancelled at idx={idx}")
                        return jsonify("Job Canceled"), 404
                    
                    # extract page from pdf
                    _trace(f"run_extraction: get_pdf_image idx={idx}")
                    chunk_file = ocr_document.get_pdf_image(local_path+filename, local_path, page_index=idx, dpi=300)
                    
                    # Set progress
                    progress = f"{idx + 1}/{nbr_pages} pages"
                    task_manager.set_progress(job_id, progress)
                    
                    # Get page ID
                    pageid = os.path.splitext(os.path.basename(chunk_file))[0]
 
                    # Choose extraction path based on the user-selected category.
                    if category in ("interventions", "interventions2"):
                        #Load image and enhance it for better OCR results (especially for handwritten forms). use _enhance_and_resize_image
                        image = Image.open(chunk_file).convert('RGB')
                        
                        # image_np = np.array(image)
                        resized_image = ocr_document.enhance_and_resize_image(image,filter=True)
                        
                        #Save resized image to send to frontend
                        debug_resized_path = os.path.join(local_path, f"{pageid}.png")
                        Image.fromarray(resized_image).save(debug_resized_path)

                         # Get document layout
                        _trace(f"run_extraction: calling get_document_layout pageid={pageid}")
                        layout = ocr_document.get_document_layout(image, split_lines_to_words=True)
                        
                        # Save layout to JSON
                        layout_json_path = os.path.join(local_path, f"output_{pageid}.json")
                        with open(layout_json_path, "w", encoding="utf-8") as f:
                            json.dump(layout, f, indent=4, ensure_ascii=False)
                        _trace(f"run_extraction: layout saved to {layout_json_path}")


                        # Detect grid/cell positions and checked boxes (for handwritten forms).
                        grid_data = grid_detector.detect_grid_cells(resized_image)
                        grid_ok = not grid_data.get("error")
                        if grid_ok:
                            grid_json_path = os.path.join(local_path, f"grid_{pageid}.json")
                            with open(grid_json_path, "w", encoding="utf-8") as f:
                                json.dump(grid_data, f, indent=4, ensure_ascii=False)
                            ocr_document.extract_tables_with_grid(CONFIG_PATH, category, grid_json_path, local_path, pageid)
                            _trace(f"run_extraction: extract_tables_with_grid done pageid={pageid}")
                    else:
                        #Load image and enhance it for better OCR results (especially for handwritten forms). use _enhance_and_resize_image
                        image = Image.open(chunk_file).convert('RGB')
                        
                        # image_np = np.array(image)
                        # resized_image = ocr_document.enhance_and_resize_image(image)

                        # Get document layout
                        _trace(f"run_extraction: calling get_document_layout pageid={pageid}")
                        layout = ocr_document.get_document_layout(image, split_lines_to_words=False)
                        #Print all lines in layout for debugging
                        for line in layout:
                            _trace(f"{line['text']}")

                        # Save layout to JSON
                        layout_json_path = os.path.join(local_path, f"output_{pageid}.json")
                        with open(layout_json_path, "w", encoding="utf-8") as f:
                            json.dump(layout, f, indent=4, ensure_ascii=False)
                        _trace(f"run_extraction: layout saved to {layout_json_path}")

                        ocr_document.extract_tables(CONFIG_PATH, category, layout_json_path, local_path, pageid)
                        _trace(f"run_extraction: extract_tables done pageid={pageid}")


                    # Save page index in project info (category already set at upload time)
                    project_data = load_project_info(local_path)
                    project_data['current_page'] = idx + 1
                    save_project_info(local_path, project_data)

                _trace(f"run_extraction: all done, returning nbr_pages={nbr_pages}")
                return {
                    "nbr_pages": nbr_pages
                }

            except Exception as e:
                import traceback
                _trace(f"run_extraction: EXCEPTION: {e}")
                _trace(traceback.format_exc())
                return {"error": str(e)}

        return task_manager.run_task(document_id, run_extraction)

    except Exception as e:
        import traceback
        _trace(f"process_ocr: EXCEPTION: {e}")
        _trace(traceback.format_exc())
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
