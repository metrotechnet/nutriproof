from flask import Blueprint, request, jsonify
import os
import sys

from api.routes.helpers import load_all_project_info

project_bp = Blueprint('project', __name__)


def _trace(msg):
    line = f"[project-route] {msg}"
    try:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
    except Exception:
        pass


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
    _trace("get_project: route hit")
    from flask import current_app
    LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
    storage_backend = current_app.config['STORAGE_BACKEND']

    project_id = request.form.get("project_id")
    _trace(f"get_project: project_id={project_id}")
    if not project_id:
        _trace("get_project: missing project_id")
        return jsonify({"error": "project_id requis"}), 400
    try:
        if storage_backend.mode == "gcs":
            _trace(f"get_project: pulling project from GCS project_id={project_id}")
            data = storage_backend.get_project_documents(project_id)
        else:
            _trace(f"get_project: hydrating local project project_id={project_id}")
            storage_backend.hydrate_project(project_id)
            data = load_all_project_info(LOCAL_FOLDER, project_id)
        if isinstance(data, dict) and "error" in data:
            _trace(f"get_project: project lookup failed project_id={project_id} error={data.get('error')}")
            return jsonify(data), 404
        _trace(f"get_project: returning project data project_id={project_id} keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
        return jsonify(data), 200
    except Exception as e:
        _trace(f"get_project: EXCEPTION project_id={project_id}: {e}")
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
        LOCAL_FOLDER = current_app.config['LOCAL_FOLDER']
        storage_backend = current_app.config['STORAGE_BACKEND']
        project_names = storage_backend.list_projects()
        return jsonify({
            "projects": project_names,
            "path": LOCAL_FOLDER,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
