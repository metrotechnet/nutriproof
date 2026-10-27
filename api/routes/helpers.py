import os
import json
import sys


def _trace(msg):
    line = f"[project-helpers] {msg}"
    try:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def load_project_info(file_path):
    """
    Charge les informations du projet depuis le fichier local.
    """
    full_path = os.path.join(file_path, "info.json")
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(file_path, payload):
    """Write JSON to disk without syncing immediately."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)


def save_project_info(file_path, project_info):
    """
    Sauvegarde les informations du projet dans le fichier local.
    """
    full_path = os.path.join(file_path, "info.json")
    save_json_file(full_path, project_info)


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
            try:
                doc_info = load_project_info(doc_path)
            except json.JSONDecodeError as exc:
                _trace(f"load_all_project_info: invalid JSON in {os.path.join(doc_path, 'info.json')}: {exc}")
                continue
            except Exception as exc:
                _trace(f"load_all_project_info: failed reading {os.path.join(doc_path, 'info.json')}: {exc}")
                continue
            if isinstance(doc_info, dict):
                project_info.append(doc_info)
            else:
                _trace(f"load_all_project_info: ignored non-dict payload in {os.path.join(doc_path, 'info.json')}")
    return project_info
