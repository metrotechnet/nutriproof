# Suppression d'un dossier document dans un projet via document_id
from flask import jsonify, request

from flask import Flask, request, jsonify, send_file, render_template
import os, json, mimetypes, uuid
import random
from waitress import serve
from py.gstorage import GSStorage
from datetime import datetime


from py.extract_tables import OCRDocument
from py.task_mngr import AsyncTaskManager
from py.clean_mngr import CleanManager


# Detect if running on Google Cloud Platform
def is_running_on_cloud():
    """Check if the application is running on Google Cloud Platform."""
    try:
        # Check for Google Cloud metadata server
        import requests
        response = requests.get(
            'http://metadata.google.internal/computeMetadata/v1/instance/',
            headers={'Metadata-Flavor': 'Google'},
            timeout=1
        )
        return response.status_code == 200
    except:
        # Also check for common cloud environment variables
        cloud_env_vars = [
            'GAE_APPLICATION',  # Google App Engine
            'GOOGLE_CLOUD_PROJECT',  # Google Cloud
            'K_SERVICE',  # Google Cloud Run
            'FUNCTION_TARGET'  # Google Cloud Functions
        ]
        return any(os.getenv(var) for var in cloud_env_vars)

# Set GCS folder based on environment
GCS_FOLDER = "nutriproof-db" 
CONFIG_PATH = "dbase/bilan_lipidique.json"
PROJECT_ID = "main"
LOCAL_FOLDER = "uploads"
APP_ENABLED = True  # Default to True, can be overridden by env variable

def create_app():

    # === Configuration ===
    global APP_ENABLED
    # === Initialisation ===
    gcs = GSStorage(LOCAL_FOLDER, GCS_FOLDER)
    ocr_document = OCRDocument(gcs)
    task_manager = AsyncTaskManager()
    clean_manager = CleanManager()
    
    #Create main project
    local_path = os.path.join(LOCAL_FOLDER, PROJECT_ID)
    os.makedirs(local_path, exist_ok=True)
    # Management des fichiers temporaires
    clean_manager.clear_folder(LOCAL_FOLDER)
    clean_manager.start()
    # gcs.delete_all_projects()
    
    #Read CONFIG_PATH to get keys order
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    #Get all key values in a list
    key_order = [item.get("label") for item in config if "label" in item]

    # Initialisation de l'application Flask
    app = Flask(__name__)

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
        """Crée un projet (dossier) local et dans GCS."""
        try:
            project_id = request.form.get("project_id")
            if not project_id:
                return jsonify({"error": "project_id requis"}), 400
            
            local_path = os.path.join(LOCAL_FOLDER, project_id)
            gcs.create_folder(local_path)
            if not os.path.exists(local_path):
                os.makedirs(local_path)

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
        """Supprime le projet local et dans GCS."""
        try:
            project_id = request.form.get("project_id")
            if not project_id:
                return jsonify({"error": "project_id requis"}), 400
            
            local_path = os.path.join(LOCAL_FOLDER, project_id)
            if  os.path.exists(local_path):
                # Suppression locale
                for root, dirs, files in os.walk(local_path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                        
                os.rmdir(local_path)
            
            # Suppression dans GCS
            try:
                gcs.delete_file(local_path)
            except Exception as e:
                pass  # Ignore GCS errors for delete
            
            return jsonify({"message": "Projet supprimé", "project_id": project_id}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Liste des projets
    @app.route("/list_projects", methods=["GET"])
    def list_projects():
        """Liste tous les projets (dossiers) dans uploads et GCS."""
        try:
           # Liste GCS
            project_names =  gcs.list_files()
            return jsonify(list(project_names)), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Fonction pour charger les informations du projet
    def load_project_info(file_path):
        """
        Remplace la fonction pour charger les informations du projet depuis la base de données SQL.
        """
        # Load form gcs
        full_path = os.path.join(file_path, "info.json")
        #create local
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        gcs.download_file(full_path)

        #Load from local file
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fonction pour sauvegarder les informations du projet
    def save_project_info(file_path, project_info):
        """
        Remplace la fonction pour sauvegarder les informations du projet dans la base de données SQL.
        """
        #save to local file
        full_path = os.path.join(file_path, "info.json")
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(project_info, f, indent=4, ensure_ascii=False)
        # Upload to gcs
        gcs.upload_file(full_path)

    #
    def load_all_project_info(project_id):
        """
        Charge toutes les informations du projet depuis la base de données SQL.
        """
        #Load all for all documents
        project_info = []
        #Loop thorugh all document folders
        for doc_folder in gcs.list_files():
            doc_info = load_project_info(os.path.join(LOCAL_FOLDER, project_id, doc_folder))
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
            import shutil, os
            folder_path = os.path.join('uploads', project_id, document_id)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)
            # Suppression GCS
            gcs.delete_file(f"uploads/{project_id}/{document_id}")
            return jsonify({'success': True}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Upload PDF
    @app.route('/upload_pdf', methods=['POST'])
    def upload_pdf():
        # Upload to GCS
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
            
            #Save to gcs bucket
            gcs.upload_file(file_path)
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
                    #download filename to local
                    os.makedirs(local_path, exist_ok=True)
                    gcs.download_file(local_path+filename)
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
                        gcs.upload_file(layout_json_path)

                        # Extract tables with Gemini
                        # ocr_document.extract_tables_with_gemini(CONFIG_PATH, layout_json_path, local_path,  pageid)
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
        #get data from gcs
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        gcs.download_file(image_path)
        if os.path.exists(image_path):
            return send_file(image_path, mimetype="image/png")
        return jsonify("Image not found"), 404

    # Get data
    @app.route("/get_data/<project_id>/<document_id>/<filename>")
    def get_data(project_id, document_id, filename):


        file_path = os.path.join(LOCAL_FOLDER, project_id, document_id, filename)
        #get data from gcs
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        gcs.download_file(file_path)
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
                
            # Upload to GCS
            gcs.upload_file(file_path)

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
            
            # download files to local
            for path in file_paths:
                if not os.path.isfile(path):
                    gcs.download_file(path)

            xls_file = ocr_document.create_xls_with_data_by_time(file_paths)
            filename = document_id + ".xls"
            return send_file(xls_file, as_attachment=True, download_name=filename)

        except Exception as e:
            return jsonify({"error": f"Server error: {str(e)}"}), 500



    
    return app


# Start  web server
if __name__ == '__main__':

    # Create app
    app = create_app()

    # Production server
    serve(app, host='0.0.0.0', port=8080)
