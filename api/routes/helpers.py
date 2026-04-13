import os
import json


def load_project_info(file_path):
    """
    Charge les informations du projet depuis le fichier local.
    """
    full_path = os.path.join(file_path, "info.json")
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project_info(file_path, project_info):
    """
    Sauvegarde les informations du projet dans le fichier local.
    """
    full_path = os.path.join(file_path, "info.json")
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(project_info, f, indent=4, ensure_ascii=False)


def load_all_project_info(local_folder, project_id):
    """
    Charge toutes les informations du projet depuis les fichiers locaux.
    """
    project_info = []
    project_path = os.path.join(local_folder, project_id)
    if not os.path.isdir(project_path):
        return {"error": "Projet introuvable"}
    for doc_folder in os.listdir(project_path):
        doc_path = os.path.join(project_path, doc_folder)
        if os.path.isdir(doc_path) and os.path.exists(os.path.join(doc_path, "info.json")):
            doc_info = load_project_info(doc_path)
            project_info.append(doc_info)
    return project_info
