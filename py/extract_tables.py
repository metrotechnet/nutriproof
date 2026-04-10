   
import os
import re
import io
import csv
import json
from unittest import result
import fitz
from datetime import datetime
from google.cloud import documentai_v1beta3 as documentai
from google.protobuf.json_format import MessageToDict
import vertexai
from vertexai.generative_models import GenerativeModel
from typing import List, Dict
import pandas as pd
import xlwt

from py.config import (
    get_project_id, get_location,
    get_ocr_processor_id
)
GEMINI_MODEL = 'gemini-2.5-flash-lite'

class OCRDocument:
    
    def __init__(self):
        self.client_ocr = documentai.DocumentProcessorServiceClient()
        vertexai.init(project=get_project_id(), location="us-east1")
        self.model = GenerativeModel(GEMINI_MODEL)

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
            with open(file_path, "rb") as file:
                file_content = file.read()

            raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
            processor_name = f"projects/{get_project_id()}/locations/{get_location()}/processors/{get_ocr_processor_id()}"
            request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
            result = self.client_ocr.process_document(request=request)
            return self.extract_blocks(result.document)
        except Exception as e:
            return {"error": str(e)}
    
    def extract_words_from_document(self, document, page_offset=0):
        """
        Extract word-level blocks directly from Document AI response.
        This provides more accurate word positioning than estimating from blocks.
        """
        word_vector = []
        
        for page in document.pages:
            page_number = page.page_number + page_offset
            
            # print(document.text)
            # Extract words from tokens (Document AI's word-level elements)
            if hasattr(page, 'tokens'):
                for token in page.tokens:
                    # Get token text from the document text
                    token_text = ""
                    if token.layout.text_anchor and token.layout.text_anchor.text_segments:
                        for segment in token.layout.text_anchor.text_segments:
                            start_idx = int(segment.start_index) if segment.start_index else 0
                            end_idx = int(segment.end_index) if segment.end_index else start_idx
                            token_text += document.text[start_idx:end_idx]
                            # print(f"Token text segment: { document.text[start_idx:end_idx]}")
                    
                    # Get token bounding box
                    if token.layout.bounding_poly and token.layout.bounding_poly.vertices:
                        token_bbox = [(v.x, v.y) for v in token.layout.bounding_poly.vertices]
                    else:
                        token_bbox = []
                    
                    # Get confidence score if available
                    confidence = token.layout.confidence if hasattr(token.layout, 'confidence') else None
                    
                    if token_text.strip():  # Only add non-empty tokens
                        word_vector.append({
                            "page": page_number,
                            "text": token_text.strip(),
                            "type": "word",
                            "bounding_box": token_bbox,
                            "confidence": confidence
                        })
            
        
        return word_vector
    
    # Extrait les blocs de texte d'un document
    def extract_blocks(self, document, page_offset=0):
        block_vector = []
        text = document.text

        for page in document.pages:
            page_number = page.page_number + page_offset
            for block in page.blocks:
                block_text = ""
                for segment in block.layout.text_anchor.text_segments:
                    block_text += text[int(segment.start_index):int(segment.end_index)]

                # Get the original bounding box
                original_bbox = [(v.x, v.y) for v in block.layout.bounding_poly.vertices]
                
                # Split text by newlines
                lines = block_text.split('\n')
                
                # Filter out empty lines
                non_empty_lines = [line for line in lines if line.strip()]
                
                if len(non_empty_lines) > 1:
                    # Multiple lines: split into separate blocks
                    # Calculate height per line
                    total_height = original_bbox[2][1] - original_bbox[0][1]
                    line_height = total_height / len(non_empty_lines)
                    
                    for i, line in enumerate(non_empty_lines):
                        # Calculate bounding box for this line
                        top_y = original_bbox[0][1] + (i * line_height)
                        bottom_y = top_y + line_height -4  # slight adjustment to avoid overlap
                        
                        line_bbox = [
                            [original_bbox[0][0], top_y],      # top-left
                            [original_bbox[1][0], top_y],      # top-right
                            [original_bbox[2][0], bottom_y],   # bottom-right
                            [original_bbox[3][0], bottom_y]    # bottom-left
                        ]
                        
                        block_vector.append({
                            "page": page_number,
                            "text": line.strip() + '\n',
                            "type": "paragraph",
                            "bounding_box": line_bbox
                        })
                elif len(non_empty_lines) == 1:
                    # Single line: keep as is
                    block_vector.append({
                        "page": page_number,
                        "text": non_empty_lines[0] + '\n',
                        "type": "paragraph",
                        "bounding_box": original_bbox
                    })
                # If no non-empty lines, don't add the block

        return block_vector

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
        Finds the next numerical value by merging the label block with the next 3 blocks
        and using Gemini to extract the value based on format description.«
        
        Args:
            blocks: List of OCR blocks
            label_block: The block containing the label
            label_text: The text of the label to search for in the block
            
        Returns:
            dict: {
                'value': extracted numerical value (float/int or None),
                'value_block': the block containing the value (or None),
                'value_bbox': bounding box of the value block (or None)
            }
        """
        if not label_block:
            return {'value': None, 'value_block': None, 'value_bbox': None}
        
        # Find the index of the label block in the blocks list
        try:
            label_block_index = blocks.index(label_block)
        except ValueError:
            # If label block is not found in the list, return None
            return {'value': None, 'value_block': None, 'value_bbox': None}
        
        # Merge the label block with the next 3 blocks
        # merged_blocks = [label_block]
        # for i in range(1, 4):  # Next 3 blocks
        #     next_block_index = label_block_index + i
        #     if next_block_index < len(blocks):
        #         merged_blocks.append(blocks[next_block_index])
        
        # Create merged text for Gemini analysis
        merged_text = " ".join([block['text'] for block in blocks])

        
        
        # Use Gemini to extract the numerical value
        try:
            # Build format instruction text
            
            prompt = f"""
                You are a data extraction assistant. Analyze the following text and extract the requested information.

                TEXT TO ANALYZE:
                "{merged_text}"

                EXTRACTION TASK:
                - Find the label "{label_text}" in the text (case-insensitive, allow minor typos)
                - Extract the next value that follows this label according to these format instructions: "{format_instructions}"
                - Apply OCR error corrections: O→0, I→1, S→5, G→6
                - Return the exact text string that matched the value

                IMPORTANT: 
                - Do NOT write code or explanations
                - Return ONLY a valid JSON object
                - If no value found, use "null" for both value and value_string

                REQUIRED JSON FORMAT:
                {{"label": "{label_text}", "value": extracted_value, "value_string": "exact_matched_text"}}
            """
            # Send request to Gemini
            
            response = self.model.generate_content(prompt)
            raw_response = response.text.strip()

            #Remove code fences
            if raw_response.startswith("```json"):
                raw_response = raw_response[7:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]

            #Convert string JSON to dict
            result = json.loads(raw_response.replace("\n", ""))
            
            # Parse Gemini response
            if not result or result['value'] == "null" :
                return {'value': None, 'value_bbox': None}
            
            # Try to convert response to number
            try:
                if isinstance(result['value'], str):
                    # Handle potential decimal comma format
                    clean_response = result['value'].replace(',', '.')
                    
                    # Check if it can be converted to float/integer
                    if self._can_convert_to_float(clean_response):
                        # Convert to float first
                        value = float(clean_response)
                        
                        # Return as int if it's a whole number
                        if value.is_integer():
                            value = int(value)
                else:
                    # Keep as string if not convertible to number
                    value = result['value']
                
                #estimate value bounding box if value_pos is given based on label block position
                value_bbox = None
                # for i in range(0, 3):  # Next 3 blocks
                #     next_block_index = label_block_index + i
                #     if result['value_string'] in blocks[next_block_index]['text'] and next_block_index < len(blocks):
                #         value_bbox = blocks[next_block_index]['bounding_box']
                for block in blocks:
                    if result['value_string'] in block['text']:
                        value_bbox = block['bounding_box']
                        break
                return {
                    'value': value,
                    'value_bbox': value_bbox
                }
                
            except (ValueError, TypeError):
                # If conversion fails, return None
                return {'value': None, 'value_bbox': None}
                
        except Exception as e:
            # If Gemini call fails, fallback to original logic
            print(f"Gemini extraction failed: {e}")

            return {'value': None, 'value_block': None, 'value_bbox': None}
    
    

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

    # Extrait les tableaux d'un document
    def extract_tables_with_gemini(self, config_json_path, ocr_json_path, project_path,  pageid ):
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
            json_data = json.dumps(ocr_data, ensure_ascii=False, indent=2)

            # Construct prompt
            prompt = f"""
                You are given these inputs:

                1. ### OCR blocks: A list of 'block'. Each block has:
                            - "page": page number
                            - "text": the recognized text
                            - "type": type of block, such as "paragraph"
                            - "bounding_box": [x, y, width, height]

                2. ### parameters: A list of string as 'parameters'
                3. ### Format: A list of instructions to format associated 'values'

                Your task:

                - For each 'parameters' in the list, find the matching 'block' by it with a word in the `text` string (case-insensitive, typo-tolerant).
                - Return the bounding box of each match 'block' in label_bbox.
                - Locate the next numerical value (float or integer) in the same 'block' or to a following block just to the right (within ±20 pixels in Y), and save it as `value`.
                - Return the bounding box of each match 'block' containing 'value' in value_bbox.
                - Use 'Format' instructions to convert 'value' as needed
                - The output JSON must keep all 'parameters' and in the same order.
                - Return the 'value' in extract_values listed by 'parameters'

                Return a single JSON object like this:

                {{
                    "label_bbox": {{
                        "Glucose": [100, 200, 50, 10]
                    }},
                    "value_bbox": {{
                        "Glucose": [160, 200, 40, 10]
                    }},
                    "extract_values": {{
                        "Glucose": 5.1,
                        "Triglycerides": null
                    }}
                }}

                Do not include explanations. Only output a valid JSON object.
                ### OCR blocks:
                {json_data}

                ### parameters:
                {target_text}

                ### Format:
                {target_parse}
            """
            # Send request
            response = self.model.generate_content(prompt)
            # Wait for response
            raw = response.text.strip()
            #Remove code fences
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
                
            #Convert string JSON to dict
            result = json.loads(raw.replace("\n", ""))
            

            # Sauvegarde ordonnée selon labels
            from collections import OrderedDict
            labels = [d['label'] for d in config_data]

            # Label bounding boxes
            label_bbox_ordered = OrderedDict((label, result['label_bbox'].get(label, None)) for label in labels)
            label_filename = f"label_bbox_{pageid}.json"
            label_path = os.path.join(project_path, label_filename)
            with open(label_path, "w", encoding="utf-8") as f:
                json.dump(label_bbox_ordered, f, indent=4, ensure_ascii=False)

            # Value bounding boxes
            value_bbox_ordered = OrderedDict((label, result['value_bbox'].get(label, None)) for label in labels)
            value_filename = f"value_bbox_{pageid}.json"
            value_path = os.path.join(project_path, value_filename)
            with open(value_path, "w", encoding="utf-8") as f:
                json.dump(value_bbox_ordered, f, indent=4, ensure_ascii=False)

            # Table data
            extract_values_ordered = OrderedDict((label, result['extract_values'].get(label, None)) for label in labels)
            table_filename = f"table_{pageid}.json"
            table_path = os.path.join(project_path, table_filename)
            with open(table_path, "w", encoding="utf-8") as f:
                json.dump(extract_values_ordered, f, indent=4, ensure_ascii=False)

            return result

        except Exception as e:
            return {"error": str(e)}
    
    # Crée un fichier CSV avec les données extraites
    def create_csv_with_data(self, file_paths, delimiter=';'):
        #Download from gcs

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