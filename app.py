# Suppression d'un dossier document dans un projet via document_id
from flask import jsonify, request

from flask import Flask, request, jsonify, send_file, render_template
import os, sys, json, mimetypes, uuid
import random
from waitress import serve
from datetime import datetime

# When running as a PyInstaller bundle, resolve paths relative to the bundle
if getattr(sys, 'frozen', False):
    _bundle_dir = sys._MEIPASS
else:
    _bundle_dir = os.path.dirname(os.path.abspath(__file__))

from api.extract_tables import OCRDocument
from api.task_mngr import AsyncTaskManager
from api.clean_mngr import CleanManager


CONFIG_PATH = os.path.join(_bundle_dir, "dbase", "bilan_lipidique.json")
PROJECT_ID = "main"
LOCAL_FOLDER = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else '.', "uploads")
APP_ENABLED = True  # Default to True, can be overridden by env variable

def create_app():

    # === Configuration ===
    global APP_ENABLED
    # === Initialisation ===
    ocr_document = OCRDocument()
    task_manager = AsyncTaskManager()
    clean_manager = CleanManager()
    
    #Create main project
    local_path = os.path.join(LOCAL_FOLDER, PROJECT_ID)
    os.makedirs(local_path, exist_ok=True)
    # Management des fichiers temporaires
    clean_manager.clear_folder(LOCAL_FOLDER)
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


    @app.get("/health")
    def health():
        """Health check endpoint"""
        return {"status": "ok"}

    # Page d'accueil
    @app.route("/")
    def home():
        if APP_ENABLED:
            return render_template("index.html")
        else:
            return render_template("maintenance.html")

    # Page de révision
    @app.route("/review")
    def review():
        return render_template("review.html")
    # === Project Service Routes ===

    # Création d'un projet
    @app.route("/create_project", methods=["POST"])
    def create_project():
        """Crée un projet (dossier) local."""
        try:
            project_id = request.form.get("project_id")
            if not project_id:
                return jsonify({"error": "project_id requis"}), 400
            
            local_path = os.path.join(LOCAL_FOLDER, project_id)
            os.makedirs(local_path, exist_ok=True)

            return jsonify({"message": "Projet créé", "project_id": project_id}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Récupération des informations d'un projet
    @app.route("/get_project", methods=["POST"])
    def get_project():
        """Retourne les infos du projet (project_info.json) pour un project_id donné."""
        project_id = request.form.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id requis"}), 400
        try:
            # Si data est binaire, décoder et charger en JSON
            data = load_all_project_info(project_id)
            if "error" in data:
                return jsonify(data), 404
            return jsonify(data), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Suppression d'un projet
    @app.route("/delete_project", methods=["POST"])
    def delete_project():
        """Supprime le projet local."""
        try:
            project_id = request.form.get("project_id")
            if not project_id:
                return jsonify({"error": "project_id requis"}), 400
            
            local_path = os.path.join(LOCAL_FOLDER, project_id)
            if os.path.exists(local_path):
                import shutil
                shutil.rmtree(local_path)
            
            return jsonify({"message": "Projet supprimé", "project_id": project_id}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Liste des projets
    @app.route("/list_projects", methods=["GET"])
    def list_projects():
        """Liste tous les projets (dossiers) dans uploads."""
        try:
            project_names = [
                d for d in os.listdir(LOCAL_FOLDER)
                if os.path.isdir(os.path.join(LOCAL_FOLDER, d))
            ]
            return jsonify(project_names), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Fonction pour charger les informations du projet
    def load_project_info(file_path):
        """
        Charge les informations du projet depuis le fichier local.
        """
        full_path = os.path.join(file_path, "info.json")
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fonction pour sauvegarder les informations du projet
    def save_project_info(file_path, project_info):
        """
        Sauvegarde les informations du projet dans le fichier local.
        """
        full_path = os.path.join(file_path, "info.json")
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(project_info, f, indent=4, ensure_ascii=False)

    #
    def load_all_project_info(project_id):
        """
        Charge toutes les informations du projet depuis les fichiers locaux.
        """
        project_info = []
        project_path = os.path.join(LOCAL_FOLDER, project_id)
        if not os.path.isdir(project_path):
            return {"error": "Projet introuvable"}
        for doc_folder in os.listdir(project_path):
            doc_path = os.path.join(project_path, doc_folder)
            if os.path.isdir(doc_path) and os.path.exists(os.path.join(doc_path, "info.json")):
                doc_info = load_project_info(doc_path)
                project_info.append(doc_info)
        return project_info

    # Suppression d'un document
    @app.route('/delete_document', methods=['POST'])
    def delete_document():
        project_id = request.form.get('project_id')
        document_id = request.form.get('document_id')
        if not project_id or not document_id:
            return jsonify({'error': 'project_id et document_id requis'}), 400
        try:
            # Suppression locale
            import shutil
            folder_path = os.path.join('uploads', project_id, document_id)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)
            return jsonify({'success': True}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Upload PDF
    @app.route('/upload_pdf', methods=['POST'])
    def upload_pdf():
        try:
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


    # Process OCR
    @app.route("/process_ocr", methods=["POST"])
    def process_ocr():
        try:
            # directory_path = os.path.join(LOCAL_FOLDER, document_id)
            
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
                        ocr_document.extract_tables(CONFIG_PATH, layout_json_path, local_path,  pageid)

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
    @app.route("/status/<job_id>", methods=["GET"])
    def status(job_id):
        try:
            return task_manager.check_status(job_id)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Cancel a job
    @app.route("/cancel/<job_id>", methods=["GET"])
    def cancel(job_id):
        try:
            return task_manager.cancel_task(job_id)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    #add a rout to set validation of document
    @app.route("/validate_document/", methods=["POST"])
    def validate_document():
        try:
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

            # Logic to validate the document
            return jsonify({"message": "Document validated successfully"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Get image
    @app.route("/get_image/<project_id>/<document_id>/<filename>")
    def get_image(project_id, document_id, filename):
        image_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
        if os.path.exists(image_path):
            return send_file(image_path, mimetype="image/png")
        return jsonify("Image not found"), 404

    # Get data
    @app.route("/get_data/<project_id>/<document_id>/<filename>")
    def get_data(project_id, document_id, filename):


        file_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
        #Create default data dict   form key_order labels
        data = {k: "" for k in key_order}
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
            #match new_data key and copy values in data
            for k in key_order:
                if k in new_data:
                    data[k] = new_data[k]
            # data['Visite'] = new_data.get('Visite', 'T0')
            return jsonify({"data_string": json.dumps(data)})
        return jsonify("File not found"), 404

    # Put data
    @app.route("/put_data", methods=["POST"])
    def put_data():
        try:
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
    @app.route("/download_xls", methods=["POST"])
    def download_xls():
        try:
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



    
    return app


# Create app instance for gunicorn
app = create_app()

# Start  web server
if __name__ == '__main__':
    # For local development
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}...")
    serve(app, host='0.0.0.0', port=port)
