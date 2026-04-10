   
import os
import re
import io
import csv
import json
import fitz
from datetime import datetime
from PIL import Image
import pyocr
import pyocr.builders
from typing import List, Dict
import pandas as pd
import xlwt

# Add Tesseract to PATH if not already there
_tesseract_path = os.environ.get("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR")
if _tesseract_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + _tesseract_path

class OCRDocument:
    
    def __init__(self):
        # Initialize pyocr tool (Tesseract)
        tools = pyocr.get_available_tools()
        if not tools:
            raise RuntimeError("No OCR tool found. Please install Tesseract.")
        self.ocr_tool = tools[0]
        print(f"Using OCR tool: {self.ocr_tool.get_name()}")

    def _can_convert_to_float(self, val):
        """Helper method to safely check if a value can be converted to float."""
        if val is None:
            return False
        try:
            float(val)
            return True
        except (ValueError, TypeError):
            return False

    # Split PDF into individual pages
    def split_pdf(self, input_pdf, output_folder):
        doc = fitz.open(input_pdf)
        chunk_paths = []
        for i in range(len(doc)):
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
            output_path = os.path.join(output_folder, f"split_{i + 1}.pdf")
            new_doc.save(output_path)
            chunk_paths.append(output_path)
        return chunk_paths

    # Split PDF into images
    def split_pdf_to_images(self, input_pdf, output_folder, image_format="png", dpi=200):
        doc = fitz.open(input_pdf)
        image_paths = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            image_path = os.path.join(output_folder, f"page_{i + 1}.{image_format}")
            pix.save(image_path)
            image_paths.append(image_path)
        return image_paths

    # Extrait une image d'une page PDF
    def get_pdf_image(self, input_pdf, output_folder, page_index=0, image_format="png", dpi=200):
        """
        Extrait la page d'index (page_index) du PDF et la sauvegarde en local.
        Args:
            input_pdf (str): Chemin du PDF source.
            output_folder (str): Dossier de sortie local.
            page_index (int): Index de la page à extraire (0 pour la première).
            image_format (str): Format d'image (par défaut png).
            dpi (int): Résolution.
        Returns:
            str: Chemin local de l'image extraite.
        """

        doc = fitz.open(input_pdf)
        if page_index < 0 or page_index >= len(doc):
            raise ValueError("Index de page hors limites")
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        image_path = os.path.join(output_folder, f"page_{page_index + 1}.{image_format}")
        pix.save(image_path)
        return image_path
    
    def get_pdf_imageNew(self, input_pdf, output_folder, page_index=0, image_format="png", dpi=150):
        """
        Extrait la résolution effective (DPI) des images de la page,
        puis exporte la page en image et sauvegarde en local.

        Args:
            input_pdf (str): Chemin du PDF source.
            output_folder (str): Dossier de sortie local.
            page_index (int): Index de la page à extraire (0 pour la première).
            image_format (str): Format d'image (par défaut png).
            dpi (int): Résolution cible pour l’export de la page.
        Returns:
            dict: {
                "image_path": chemin local de l’image extraite,
                "images_dpi": liste des DPI des images trouvées
            }
        """
        doc = fitz.open(input_pdf)

        if page_index < 0 or page_index >= len(doc):
            raise ValueError("Index de page hors limites")

        page = doc[page_index]

        # --- Étape 1 : Extraire le premier DPI trouvé ---
        measured_dpi= dpi
        for img in page.get_images(full=True):
            xref = img[0]
            width, height = img[2], img[3]

            # Parcours des blocs pour trouver le bloc image correspondant
            for block in page.get_text("dict")["blocks"]:
                if block["type"] == 1 and block.get("image"):
                    rect = fitz.Rect(block["bbox"])
                    display_w, display_h = rect.width, rect.height
                    if display_w > 0 and display_h > 0:
                        dpi_x = width / (display_w / 72)
                        dpi_y = height / (display_h / 72)
                        measured_dpi = (dpi_x, dpi_y)
                        break  # On prend seulement le premier
            if measured_dpi:
                break

        # --- Étape 2 : Export de la page en image ---
            # Si aucun DPI trouvé, on met une valeur par défaut (150)
        export_dpi = int(round(measured_dpi[0])) if measured_dpi else dpi
        pix = page.get_pixmap(dpi=export_dpi)
        image_path = os.path.join(output_folder, f"page_{page_index + 1}.{image_format}")
        pix.save(image_path)

        return image_path
    
    # Récupère le nombre de pages d'un PDF
    def get_pdf_page_count(self, pdf_path):
        return len(fitz.open(pdf_path))

    # Récupère la mise en page d'un document
    def get_document_layout(self, file_path, mime_type="application/pdf"):
        try:
            image = Image.open(file_path)
            lang = "fra+eng"

            # Use LineBoxBuilder to get lines with bounding boxes
            line_boxes = self.ocr_tool.image_to_string(
                image,
                lang=lang,
                builder=pyocr.builders.LineBoxBuilder()
            )

            block_vector = []
            for line_box in line_boxes:
                text = line_box.content.strip()
                if not text:
                    continue
                # line_box.position is ((x1, y1), (x2, y2))
                pos = line_box.position
                bbox = [
                    [pos[0][0], pos[0][1]],  # top-left
                    [pos[1][0], pos[0][1]],  # top-right
                    [pos[1][0], pos[1][1]],  # bottom-right
                    [pos[0][0], pos[1][1]],  # bottom-left
                ]
                block_vector.append({
                    "page": 1,
                    "text": text + "\n",
                    "type": "paragraph",
                    "bounding_box": bbox
                })

            return block_vector
        except Exception as e:
            return {"error": str(e)}
    
  # Extrait les tableaux d'un document
    def extract_tables(self, config_json_path, ocr_json_path, project_path,  pageid ):
        try:
            #Read config
            with open(config_json_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # target_text = [item["text"] for item in config_data if "text" in item]
            target_text = {param["label"]: param["text"] for param in config_data if "label" in param and "text" in param}
            target_parse = {param["label"]: param["parse"] for param in config_data if "label" in param and "parse" in param}
            # Load OCR layout data
            with open(ocr_json_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            label_bboxes = {}
            value_bboxes = {}
            extract_values = {}
            for param in config_data:
                if "label" not in param or "text" not in param:
                    continue
                label = param["label"]
                text = param["text"]
                block = self.find_matching_block(ocr_data, text)
                if block:
                    label_bboxes[label] = block['bounding_box']
                    # Find numerical value for this label
                    value_result = self.find_next_value(ocr_data, block, text, target_parse.get(label))
                    if value_result['value'] is not None:
                        extract_values[label] = value_result['value']
                        value_bboxes[label] = value_result['value_bbox']
                   
                        

            # Sauvegarde ordonnée selon labels
            from collections import OrderedDict
            labels = [d['label'] for d in config_data]

            # Label bounding boxes
            label_bbox_ordered = OrderedDict((label, label_bboxes.get(label, None)) for label in labels)
            label_filename = f"label_bbox_{pageid}.json"
            label_path = os.path.join(project_path, label_filename)
            with open(label_path, "w", encoding="utf-8") as f:
                json.dump(label_bbox_ordered, f, indent=4, ensure_ascii=False)

            # Value bounding boxes
            value_bbox_ordered = OrderedDict((label, value_bboxes.get(label, None)) for label in labels)
            value_filename = f"value_bbox_{pageid}.json"
            value_path = os.path.join(project_path, value_filename)
            with open(value_path, "w", encoding="utf-8") as f:
                json.dump(value_bbox_ordered, f, indent=4, ensure_ascii=False)

            # Table data
            extract_values_ordered = OrderedDict((label, extract_values.get(label, None)) for label in labels)
            table_filename = f"table_{pageid}.json"
            table_path = os.path.join(project_path, table_filename)
            with open(table_path, "w", encoding="utf-8") as f:
                json.dump(extract_values_ordered, f, indent=4, ensure_ascii=False)

            return {
                "label_bbox": label_bbox_ordered,
                "value_bbox": value_bbox_ordered,
                "extract_values": extract_values_ordered
            }

        except Exception as e:
            return {"error": str(e)}

    def find_next_value(self, blocks, label_block, label_text, format_instructions=None):
        """
        Finds the next numerical value near the label block using spatial proximity.
        Looks for blocks to the right of or just below the label, then extracts
        the first number found.
        
        Args:
            blocks: List of OCR blocks
            label_block: The block containing the label
            label_text: The text of the label to search for
            format_instructions: Parse hint from config (e.g. "a number", "a string with digits")
            
        Returns:
            dict with 'value' and 'value_bbox'
        """
        if not label_block:
            return {'value': None, 'value_bbox': None}

        try:
            label_idx = blocks.index(label_block)
        except ValueError:
            return {'value': None, 'value_bbox': None}

        # Get label bounding box center Y and right edge X
        label_bbox = label_block['bounding_box']
        label_cy = (label_bbox[0][1] + label_bbox[2][1]) / 2
        label_right = label_bbox[1][0]
        label_height = abs(label_bbox[2][1] - label_bbox[0][1])

        # Determine parsing mode from format_instructions
        parse_mode = "number"  # default
        allowed_values = None
        if format_instructions:
            fi = format_instructions.lower()
            if "string" in fi and "digit" in fi:
                parse_mode = "digits_string"
            if "one of" in fi:
                # Extract allowed values like "one of 0, 6, 18"
                match = re.search(r'one of\s+([\d,\s\-]+)', fi)
                if match:
                    allowed_values = [v.strip() for v in match.group(1).split(',')]

        # OCR error corrections
        ocr_corrections = {'O': '0', 'I': '1', 'S': '5', 'G': '6'}

        def apply_ocr_fixes(text):
            result = text
            for wrong, correct in ocr_corrections.items():
                result = result.replace(wrong, correct)
            return result

        def extract_number(text):
            """Extract a number (float or int) from text."""
            # Try to find a number pattern (supports comma and period as decimal)
            numbers = re.findall(r'-?\d+[.,]\d+|-?\d+', text)
            if numbers:
                num_str = numbers[0].replace(',', '.')
                try:
                    val = float(num_str)
                    return int(val) if val == int(val) else val
                except ValueError:
                    pass
            return None

        def extract_digits_string(text):
            """Extract a string of 3-4 consecutive digits."""
            match = re.search(r'\d{3,4}', apply_ocr_fixes(text))
            return match.group(0) if match else None

        # Score candidate blocks by spatial proximity
        candidates = []
        for i, block in enumerate(blocks):
            if i == label_idx:
                continue
            bbox = block['bounding_box']
            block_cx = (bbox[0][0] + bbox[1][0]) / 2
            block_cy = (bbox[0][1] + bbox[2][1]) / 2
            block_left = bbox[0][0]

            # Must be to the right of label or just below
            dy = block_cy - label_cy
            dx = block_left - label_right

            # Candidate: same line (within label_height tolerance) and to the right
            same_line = abs(dy) < label_height * 1.2 and dx > -20
            # Candidate: just below (within 2x label height) and roughly aligned
            just_below = 0 < dy < label_height * 3 and abs(block_left - label_bbox[0][0]) < label_height * 3

            if same_line or just_below:
                # Priority: same-line blocks first, then below; closer is better
                priority = 0 if same_line else 1
                distance = abs(dx) + abs(dy)
                candidates.append((priority, distance, i, block))

        # Sort: same-line first, then by distance
        candidates.sort(key=lambda c: (c[0], c[1]))

        # Try to extract value from candidates
        for _, _, _, block in candidates:
            text = block['text'].strip()
            if not text:
                continue

            value = None
            if parse_mode == "digits_string":
                value = extract_digits_string(text)
            else:
                value = extract_number(text)
                # If we got a number but there are allowed values, check
                if value is not None and allowed_values:
                    if str(int(value) if isinstance(value, float) and value == int(value) else value) not in allowed_values:
                        # Apply OCR fixes and retry
                        value = extract_number(apply_ocr_fixes(text))

            if value is not None:
                # Handle allowed values constraint
                if allowed_values:
                    str_val = str(int(value)) if isinstance(value, (int, float)) else str(value)
                    if str_val not in allowed_values:
                        continue  # Skip, not in allowed set

                return {
                    'value': value,
                    'value_bbox': block['bounding_box']
                }

        return {'value': None, 'value_bbox': None}
    
    

        # create a function:    For each 'parameters' in the list, find the matching 'block' by it with a word in the `text` string (case-insensitive, typo-tolerant)
    def find_matching_block(self, blocks, target):
        """
        Find a matching block by searching for target text(s).
        
        Args:
            blocks: List of OCR blocks
            target: Either a string or a list of strings to search for
            
        Returns:
            The first block that matches any of the target strings, or None if no match found
        """
        # Convert single string to list for uniform processing
        targets = [target] if isinstance(target, str) else target
        
        # Try to match any of the target strings
        for target_text in targets:
            pattern = re.compile(re.escape(target_text), re.IGNORECASE)
            for block in blocks:
                if pattern.search(block['text']):
                    return block
        return None

   
    # Crée un fichier CSV avec les données extraites
    def create_csv_with_data(self, file_paths, delimiter=';'):
        headers = [
            "Section", "Centre", "Participants", "Sequence", "Traitement", "Visites",
            "glu-15", "ins-15", "glu0", "ins0", "glu30", "ins30", "glu60", "ins60", "glp1", "pyy", "ghrelin", "leptine", "il6", "crp_elisa", "chol", "tg", "hdlc", "ldlc", "chol_hdlc", "nhdlc"
        ]
        all_rows = [
            [f"Projet (abrev ) :;SAT2;;;;;Note pour les colonnes de variables : ;;;;;;;;;;;;;;;;;;;"],
            [";;;;;;Une cellule vide sera ignorée. ;;;;;;;;;;;;;;;;;;;"],
            [";;;;;;Une cellule contenant un point écrasera la donnée dans la base de données;;;;;;;;;;;;;;;;;;;"],
            [";;;;;;;;;;;;;;;;;;;;;;;;;"],
            ["Informations de projet;;;;;;Liste de variables ( à remplir );;;;;;;;;;;;;;;;;;;"],
            [";".join(headers)],
        ]
        param_mapping = {
            "Matricule": "Participants",
            "Visite": "Visites",
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
        

        for idx, path in enumerate(file_paths):
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                print(json_data)
                #find name mapping and save data in right colomn as specified in headers
                row = [""] * len(headers)
                for key, value in param_mapping.items():
                    if key in json_data:
                        if isinstance(value, list):
                            for v in value:
                                val = json_data[key]
                                if val and self._can_convert_to_float(val):
                                    row[headers.index(v)] = float(val)
                        else:
                            val = json_data[key]
                            if val and self._can_convert_to_float(val):
                                row[headers.index(value)] = float(val)
                row[0] = "Projet"  # Section
                row[1] = "INAF"  # Centre
                row[5] = "T0"  # Sequence
                
                #Convertie la liste row dans une seule string séparé par des ;
                row_str = ";".join([str(item) for item in row])
                #Replace . by ,
                row_str = row_str.replace(".", ",")
                all_rows.append([row_str])
    
   
        # # Ecriture dans un buffer mémoire
        buffer = io.StringIO()
        for row in all_rows:
            buffer.write(row[0] + '\n')
        # Ajoute le BOM UTF-8 pour Excel et accents
        content = '\ufeff' + buffer.getvalue()
        binary_buffer = io.BytesIO()
        binary_buffer.write(content.encode('utf-8'))
        binary_buffer.seek(0)
        return binary_buffer
       

    def create_xls_with_data(self,  file_paths):
        """
        Crée un fichier Excel .xls en mémoire à partir des fichiers JSON de résultats.
        Retourne un buffer binaire prêt à être envoyé.
        """

        headers = [
            "Section", "Centre", "Participants", "Sequence", "Traitement", "Visites",
            "glu-15", "ins-15", "glu0", "ins0", "glu30", "ins30", "glu60", "ins60", "glp1", "pyy", "ghrelin", "leptine", "il6", "crp_elisa", "chol", "tg", "hdlc", "ldlc", "chol_hdlc", "nhdlc"
        ]
        all_rows = [
            ["Projet (abrev ) :", "SAT2", "", "", "", "", "Note pour les colonnes de variables :", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "Une cellule vide sera ignorée.", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "Une cellule contenant un point écrasera la donnée dans la base de données", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["Informations de projet", "", "", "", "", "", "Liste de variables ( à remplir )", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            headers,
        ]
        param_mapping = {
            "Matricule": "Participants",
            "Visite": "Visites",
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

        # Remplir les lignes de données
        for idx, path in enumerate(file_paths):
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                row = ["" for _ in headers]
                for key, value in param_mapping.items():
                    if key in json_data:
                        if isinstance(value, list):
                            for v in value:
                                val = json_data[key]
                                if val and self._can_convert_to_float(val):
                                    row[headers.index(v)] = float(val)
                        else:
                            val = json_data[key]
                            if val and self._can_convert_to_float(val):
                                row[headers.index(value)] = float(val)
                row[0] = "Projet"  # Section
                row[1] = "INAF"  # Centre
                row[5] = "T0"  # Sequence
                all_rows.append(row)

        # Création du classeur Excel
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Feuille1')
        # Définir un style de police pour l'en-tête (gras, taille 12)
        header_style = xlwt.easyxf('align: vert centre, horiz center; pattern: pattern solid, fore_colour yellow;')
        for row_idx, row in enumerate(all_rows):
            for col_idx, value in enumerate(row):
                if row_idx == 5:
                    ws.write(row_idx, col_idx, value, header_style)
                else:
                    ws.write(row_idx, col_idx, value)

        # Sauvegarde dans un buffer mémoire
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    def create_xls_with_data_by_time(self, file_paths):
        """
        Crée un fichier Excel .xls en mémoire à partir des fichiers JSON de résultats.
        Associe les colonnes Glucose et Insuline avec l'item Temps (ex: si Temps=-15, met la valeur de Glucose dans glu-15 et Insuline dans ins-15).
        Retourne un buffer binaire prêt à être envoyé.
        """
        headers = [
            "Section", "Centre", "Participants", "Sequence", "Traitement", "Visites",
            "glu-15", "ins-15", "glu0", "ins0", "glu30", "ins30", "glu60", "ins60", "glp1", "pyy", "ghrelin", "leptine", "il6", "crp_elisa", "chol", "tg", "hdlc", "ldlc", "chol_hdlc", "nhdlc"
        ]
        all_rows = [
            ["Projet (abrev ) :", "SAT2", "", "", "", "", "Note pour les colonnes de variables :", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "Une cellule vide sera ignorée.", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "Une cellule contenant un point écrasera la donnée dans la base de données", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["Informations de projet", "", "", "", "", "", "Liste de variables ( à remplir )", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            headers,
        ]
        param_mapping = {
            "Matricule": "Participants",
            "Visite": "Visites",
            "Protéine C réactive": "crp_elisa",
            "Cholestérol total": "chol",
            "Triglycérides": "tg",
            "Cholestérol-HDL": "hdlc",
            "Cholestérol-LDL": "ldlc",
            "Cholestérol non-HDL": "nhdlc",
            "Ratio Chol tot./Chol-HDL": "chol_hdlc",

        }

        temps_map = {
            "-15": ("glu-15", "ins-15"),
            "0": ("glu0", "ins0"),
            "30": ("glu30", "ins30"),
            "60": ("glu60", "ins60"),
        }

        # Collecte des lignes par combo Matricule/Visite
        rows_by_combo = {}
        for idx, path in enumerate(file_paths):
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                row = ["" for _ in headers]
                # Mapping direct
                for key, value in param_mapping.items():
                    if key in json_data:
                        val = json_data[key]
                        if val and self._can_convert_to_float(val):
                            row[headers.index(value)] = float(val)
                # Temps par défaut à 0 si absent ou non convertible
                temps_val = json_data.get("Temps", None)
                if not self._can_convert_to_float(temps_val):
                    temps_val = 0
                temps_val = str(int(float(temps_val)))
                if temps_val in temps_map:
                    glu_col, ins_col = temps_map[temps_val]
                    if "Glucose" in json_data and self._can_convert_to_float(json_data["Glucose"]):
                        row[headers.index(glu_col)] = float(json_data["Glucose"])
                    if "Insuline" in json_data and self._can_convert_to_float(json_data["Insuline"]):
                        row[headers.index(ins_col)] = float(json_data["Insuline"])
                row[0] = "Projet"  # Section
                row[1] = "INAF"  # Centre
                # Visite par défaut à 0 si absent ou non convertible
                visite_val = json_data.get("Visite", None)
                if not self._can_convert_to_float(visite_val):
                    visite_val = 0
                row[5] = "T" + str(int(float(visite_val)))  # Sequence

                # Fusionne par combo Matricule/Visite
                matricule = str(json_data.get("Matricule", ""))
                visite = str(int(float(visite_val)))
                combo_key = f"{matricule}|{visite}"
                if combo_key not in rows_by_combo:
                    rows_by_combo[combo_key] = row
                else:
                    # Fusionne les valeurs (remplit les colonnes vides)
                    for i in range(len(row)):
                        if row[i] != "" and rows_by_combo[combo_key][i] == "":
                            rows_by_combo[combo_key][i] = row[i]
                            
        # Ajoute les lignes fusionnées à all_rows
        for merged_row in rows_by_combo.values():
            all_rows.append(merged_row)

        # Création du classeur Excel
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Feuille1')
        header_style = xlwt.easyxf('align: vert centre, horiz center; pattern: pattern solid, fore_colour yellow;')
        for row_idx, row in enumerate(all_rows):
            for col_idx, value in enumerate(row):
                if row_idx == 5:
                    ws.write(row_idx, col_idx, value, header_style)
                else:
                    ws.write(row_idx, col_idx, value)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output