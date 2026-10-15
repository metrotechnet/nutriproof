from flask import Blueprint, request, jsonify
import os

from api.routes.helpers import load_all_project_info

project_bp = Blueprint('project', __name__)


# Création d'un projet
@project_bp.route("/create_project", methods=["POST"])
def create_project():
    """Crée un projet (dossier) local."""
    try:
        from flask import current_app
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']

        project_id = request.form.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id requis"}), 400
        
        local_path = os.path.join(LOCAL_FOLDER, project_id)
        os.makedirs(local_path, exist_ok=True)

        return jsonify({"message": "Projet créé", "project_id": project_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Récupération des informations d'un projet
@project_bp.route("/get_project", methods=["POST"])
def get_project():
    """Retourne les infos du projet (project_info.json) pour un project_id donné."""
    from flask import current_app
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    storage_backend = current_app.config['STORAGE_BACKEND']

    project_id = request.form.get("project_id")
    if not project_id:
        return jsonify({"error": "project_id requis"}), 400
    try:
        if storage_backend.mode == "gcs":
            data = storage_backend.get_project_documents(project_id)
        else:
            storage_backend.hydrate_project(project_id)
            data = load_all_project_info(LOCAL_FOLDER, project_id)
        if isinstance(data, dict) and "error" in data:
            return jsonify(data), 404
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Suppression d'un projet
@project_bp.route("/delete_project", methods=["POST"])
def delete_project():
    """Supprime le projet local."""
    try:
        from flask import current_app
        storage_backend = current_app.config['STORAGE_BACKEND']

        project_id = request.form.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id requis"}), 400
        
        storage_backend.delete_project(project_id)
        
        return jsonify({"message": "Projet supprimé", "project_id": project_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Liste des projets
@project_bp.route("/list_projects", methods=["GET"])
def list_projects():
    """Liste tous les projets (dossiers) dans uploads."""
    try:
        from flask import current_app
        storage_backend = current_app.config['STORAGE_BACKEND']
        project_names = storage_backend.list_projects()
        return jsonify(project_names), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
