

import os
import io
import json
import xlwt
from google.cloud import storage
from datetime import datetime
import fitz

# === CONFIGURATION ===
BUCKET_NAME = "nutriss-bucket"
GCS_FOLDERS = [
    "gs://nutriss-bucket/truth_database/dboulanger/0d7f2f64",
    "gs://nutriss-bucket/truth_database/dboulanger/17d4e5dc",
    "gs://nutriss-bucket/truth_database/dboulanger/1b95f0df",
    "gs://nutriss-bucket/truth_database/dboulanger/22433577",
    "gs://nutriss-bucket/truth_database/dboulanger/3dc81e85",
    "gs://nutriss-bucket/truth_database/dboulanger/4a03878d",
    "gs://nutriss-bucket/truth_database/dboulanger/569c1f5a",
    "gs://nutriss-bucket/truth_database/dboulanger/5f7cd982",
    "gs://nutriss-bucket/truth_database/dboulanger/a7604924",
    "gs://nutriss-bucket/truth_database/dboulanger/c691574f",
    "gs://nutriss-bucket/truth_database/dboulanger/e1a0f733",
    "gs://nutriss-bucket/truth_database/dboulanger/f5248412",
]
# Chemin vers le fichier de credentials Google Cloud (optionnel)
GOOGLE_APPLICATION_CREDENTIALS = "D:\\Nutriss\\nutriss-92f322006a05.json"

# Récupère le nombre de pages d'un PDF
def get_pdf_page_count(pdf_path):
    return len(fitz.open(pdf_path))
    
def download_json_from_gcs(bucket_name, gcs_path, local_dir):
    """
    Télécharge tous les fichiers table_page_*.json d'un dossier GCS vers un dossier local.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    prefix = gcs_path.replace(f"gs://{bucket_name}/", "")
    blobs = bucket.list_blobs(prefix=prefix)
    local_files = []
    for blob in blobs:
        local_path = os.path.join(local_dir, os.path.basename(blob.name))
        blob.download_to_filename(local_path)
        local_files.append(local_path)
    return local_files

def add_data_rows(file_paths, all_rows):
    headers = [
        "Section", "Centre", "Participants", "Sequence", "Traitement", "Visites",
        "glu-15", "ins-15", "glu0", "ins0", "glu30", "ins30", "glu60", "ins60", "glp1", "pyy", "ghrelin", "leptine", "il6", "crp_elisa", "chol", "tg", "hdlc", "ldlc", "chol_hdlc", "nhdlc"
    ]
    param_mapping = {
        "Matricule": "Participants",
        "Protéine C réactive": "crp_elisa",
        "Cholestérol total": "chol",
        "Triglycérides": "tg",
        "Cholestérol-HDL": "hdlc",
        "Cholestérol-LDL": "ldlc",
        "Cholestérol non-HDL": "nhdlc",
        "Ratio Chol tot./Chol-HDL": "chol_hdlc",
        "Glucose": ["glu-15", "glu0", "glu30", "glu60"],
        "Insuline": ["ins-15", "ins0", "ins30", "ins60"]
    }
    # Si on veut fusionner plusieurs dossiers, on peut passer append_rows (liste de lignes à ajouter)
    # Remplir les lignes de données
    for idx, path in enumerate(file_paths):
        filename = os.path.basename(path)
        if filename.startswith('table_page') and filename.endswith('.json'):
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                row = ["" for _ in headers]
                for key, value in param_mapping.items():
                    if key in json_data:
                        if isinstance(value, list):
                            for v in value:
                                val = json_data[key]
                                if(val):
                                    row[headers.index(v)] = float(val)
                        else:
                            val = json_data[key]
                            if(val):
                                row[headers.index(value)] = float(val)
            all_rows.append(row)
    return all_rows

    
def create_xls_with_data(output_xls, data_rows):
    headers = [
        "Section", "Centre", "Participants", "Sequence", "Traitement", "Visites",
        "glu-15", "ins-15", "glu0", "ins0", "glu30", "ins30", "glu60", "ins60", "glp1", "pyy", "ghrelin", "leptine", "il6", "crp_elisa", "chol", "tg", "hdlc", "ldlc", "chol_hdlc", "nhdlc"
    ]
    all_rows = [
        ["Projet (abrev ) :", "", "", "", "", "", "Note pour les colonnes de variables :", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "Une cellule vide sera ignorée.", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "Une cellule contenant un point écrasera la donnée dans la base de données", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["Informations de projet", "", "", "", "", "", "Liste de variables ( à remplir )", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        headers,
    ]
    
    # Si on veut fusionner plusieurs dossiers, on peut passer append_rows (liste de lignes à ajouter)
    all_rows.extend(data_rows)

            
    wb = xlwt.Workbook()
    ws = wb.add_sheet('Feuille1')
    for row_idx, row in enumerate(all_rows):
        for col_idx, value in enumerate(row):
            ws.write(row_idx, col_idx, value)
    wb.save(output_xls)
    
def create_info_json(subfolder_path):
    """
    Crée un fichier info.json dans le sous-dossier donné, si il n'existe pas déjà.
    """
    info_path = os.path.join(subfolder_path, "info.json")
    if os.path.exists(info_path):
        return
    # Recherche d'un PDF ou d'un nom de fichier dans le dossier
    files = os.listdir(subfolder_path)
    pdf_file = next((f for f in files if f.lower().endswith('.pdf')), None)
    nbrPages = get_pdf_page_count(os.path.join(subfolder_path, pdf_file))
    # Construction du contenu info.json
    info = {
        "project_id": "main",
        "document_id": os.path.basename(subfolder_path),
        "filename": pdf_file or "",
        "upload_date": datetime.now().isoformat(),
        "nbr_pages": nbrPages,
        "current_page": 0,
        "v1": True,
        "v2": True
    }
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=4, ensure_ascii=False)
    print(f"info.json créé dans {subfolder_path}")
                
if __name__ == "__main__":
    # Utilise la variable d'environnement si définie
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
    all_data_rows = []

    for gcs_path in GCS_FOLDERS:
        local_dir = os.path.join("D:\\Nutriss\\ground_truth",os.path.basename(gcs_path))
        os.makedirs(local_dir, exist_ok=True)
        print(f"Téléchargement des JSON depuis {gcs_path}...")
        json_files = download_json_from_gcs(BUCKET_NAME, gcs_path, local_dir)
        create_info_json(local_dir)
        if not json_files:
            print(f"Aucun fichier table_page_*.json trouvé dans {gcs_path}")
            continue
        all_data_rows = add_data_rows(json_files, all_data_rows)
        
        # On fusionne toutes les lignes de données (sauf l'entête et les lignes d'intro)
    # À la fin, on regénère le fichier global fusionné
    print("Création du fichier Excel global all_results.xls ...")
    create_xls_with_data("D:\\Nutriss\\ground_truth\\all_results.xls", all_data_rows)
    print("Fichier Excel global sauvegardé : all_results.xls")
