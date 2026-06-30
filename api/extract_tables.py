   
import os
import sys
import re
import io
import csv
import json
import ctypes
from contextlib import contextmanager
import fitz
from datetime import datetime
from PIL import Image, ImageOps, ImageFilter
import pyocr
import pyocr.builders
from typing import List, Dict
import pandas as pd
import xlwt
import numpy as np


def _trace(msg):
    """Flush-immediately trace so messages survive PyInstaller buffering."""
    line = f"[ocr-trace] {msg}"
    try:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception:
        pass

# Add Tesseract to PATH if not already there
if sys.platform == "win32":
    _default_tesseract = r"C:\Program Files\Tesseract-OCR"
elif sys.platform == "darwin":
    _default_tesseract = "/opt/homebrew/bin"
else:
    _default_tesseract = "/usr/bin"
_tesseract_path = os.environ.get("TESSERACT_PATH", _default_tesseract)
if _tesseract_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + _tesseract_path


# ---------------------------------------------------------------------------
# Handwriting OCR configuration
# ---------------------------------------------------------------------------
# Tesseract 4/5 already uses the LSTM engine by default (OEM_DEFAULT resolves
# to LSTM_ONLY when LSTM data is present), so we don't need to flip OEM here.
# What we DO need for handwritten forms is to disable the printed-text
# dictionaries (otherwise Tesseract snaps handwritten tokens onto French/Eng
# vocabulary words and mangles numeric/handwritten content).
HANDWRITING_TESS_VARS = {
    # Disable all built-in language model dictionaries.
    "load_system_dawg":          "F",
    "load_freq_dawg":            "F",
    "load_unambig_dawg":         "F",
    "load_punc_dawg":            "F",
    "load_number_dawg":          "F",
    "load_bigram_dawg":          "F",
    # Remove dictionary penalties so non-dictionary words aren't down-weighted.
    "language_model_penalty_non_dict_word":      "0",
    "language_model_penalty_non_freq_dict_word": "0",
    # Keep spacing as-is (handwriting often has wide / irregular spacing).
    "preserve_interword_spaces": "1",

    # --- Sensitivity tuning for small / faint handwritten marks --------------
    # Tesseract aggressively drops small connected components it considers
    # "noise" (dust, scanner speckle). On handwritten forms this also wipes
    # out check marks, isolated punctuation (commas, periods, accents),
    # apostrophes, short ticks and crossed-out cells. We relax those filters
    # so small / thin / isolated shapes survive into the recognizer.

    # Don't reject whole words/rows just because their connected components
    # look noisy in size.
    "textord_noise_rejwords":      "F",
    "textord_noise_rejrows":       "F",
    # Lower the size ratio under which a blob is called noise (default 0.7).
    "textord_noise_sizefraction":  "0.2",
    # Lower the row-x-height ratio used to discard tiny blobs (default 0.4).
    "textord_noise_sizelimit":     "0.1",
    # Allow much smaller character x-heights (default 10 pixels -> 6).
    "textord_min_xheight":         "6",
    # Don't drop blobs that look "too tall/thin" — handwritten 1s, accents,
    # apostrophes, vertical bars are exactly that shape.
    "textord_noise_normratio":     "1.0",
    # Lower the per-blob noise count threshold so a single small mark isn't
    # auto-classified as noise (default 10).
    "textord_noise_snmin":         "0.3",
    # Don't trust dictionary/context to gate character acceptance — accept
    # what the classifier sees.
    "tessedit_enable_doc_dict":    "0",
    # Increase the number of segmentation states kept per blob so unusual
    # handwritten shapes get more chances to be recognized.
    "tessedit_certainty_threshold": "-20",
    # Don't reject low-confidence characters outright (default keeps them
    # blank). We want them surfaced even if uncertain — the human reviews.
    "tessedit_zero_rejection":     "T",
    # Disable image inversion attempts that can blank out faint pencil.
    "tessedit_do_invert":          "0",
}


@contextmanager
def _handwriting_mode():
    """Context manager that patches pyocr.libtesseract.tesseract_raw.init so
    that every Tesseract handle created inside the block has the handwriting
    variables applied right after initialization (and before recognition).

    No-op if the libtesseract backend is not installed.
    """
    try:
        from pyocr.libtesseract import tesseract_raw  # type: ignore
    except Exception as e:
        _trace(f"_handwriting_mode: libtesseract not available ({e}), skipping")
        yield
        return

    orig_init = tesseract_raw.init

    def _patched_init(lang=None):
        handle = orig_init(lang=lang)
        try:
            lib = tesseract_raw.g_libtesseract
            for var, val in HANDWRITING_TESS_VARS.items():
                lib.TessBaseAPISetVariable(
                    ctypes.c_void_p(handle),
                    var.encode("utf-8"),
                    val.encode("utf-8"),
                )
        except Exception as e:
            _trace(f"_handwriting_mode: failed to set vars: {e}")
        return handle

    tesseract_raw.init = _patched_init
    try:
        yield
    finally:
        tesseract_raw.init = orig_init


@contextmanager
def _null_context():
    """No-op context manager used when handwriting mode is disabled."""
    yield

class OCRDocument:
    def __init__(self, ocr_engine='paddle'):
        """
        ocr_engine: 'tesseract' (pyocr)
        """
        self.ocr_engine = ocr_engine
        # Initialize pyocr tool (Tesseract)
        _trace("OCRDocument.__init__: calling pyocr.get_available_tools()")
        tools = pyocr.get_available_tools()
        _trace(f"OCRDocument.__init__: tools={[t.get_name() for t in tools]}")
        if not tools:
            _trace("OCRDocument.__init__: NO OCR TOOL FOUND")
            raise RuntimeError("No OCR tool found. Please install Tesseract.")
        self.ocr_tool = None
        for t in tools:
            name = t.get_name()
            if 'C-API' in name or 'libtesseract' in name.lower():
                self.ocr_tool = t
                _trace(f"OCRDocument.__init__: selected C-API tool: {name}")
                break
        if self.ocr_tool is None:
            self.ocr_tool = tools[0]
            _trace(f"OCRDocument.__init__: C-API not found, falling back to: {self.ocr_tool.get_name()}")
        try:
            langs = self.ocr_tool.get_available_languages()
            _trace(f"OCRDocument.__init__: tool={self.ocr_tool.get_name()} langs={langs}")
        except Exception as e:
            _trace(f"OCRDocument.__init__: get_available_languages failed: {e}")
        print(f"Using OCR tool: {self.ocr_tool.get_name()}")
    def enhance_and_resize_image(self, crop, scale=1.0, filter=False):
        """
        Enhance the cropped image: binarize, filter, resize, and convert to RGB numpy array.
        Args:
            crop: PIL Image to process.
            scale: Resize factor (default 1.0).
        Returns:
           Numpy array (RGB, uint8) of the processed image.
        """
        # Ensure grayscale for binarization
        if crop.mode != 'L':
            crop = crop.convert('L')
        crop = crop.point(lambda p: 0 if p < 180 else 255, '1')

        if filter:
            # Morphological dilation  using np
            crop = crop.filter(ImageFilter.MinFilter(3))
            # crop = crop.filter(ImageFilter.MinFilter(3))
        
        if(scale != 1.0):
            w, h = crop.size
            new_size = (int(w * scale), int(h * scale))
            crop = crop.resize(new_size, Image.LANCZOS).convert('RGB')

        return np.array(crop.convert('RGB'))
    
    def read_row0_digits(self, cells, gray_img=None):
        """
        OCR manuscript digits in row 0 using digit-only Tesseract config.
        Returns a list of (col, text) for each cell in row 0.
        """
        import re
        results = []
        row0_cells = [c for c in cells if c.get("row") == 0]
        for cell in row0_cells:
            bbox = self._cell_rect(cell)
            if not bbox:
                continue
            x1, y1, x2, y2 = map(int, bbox)
            top = max(y1, y1+(y2-y1) * 0.25)
            crop = gray_img.crop((x1, top, x2, y2)) if gray_img else None
            if crop is None:
                continue
            # Enhance image: binarize (simple threshold)
            crop = crop.point(lambda p: 0 if p < 180 else 255, '1')
            crop = crop.filter(ImageFilter.MinFilter(3))
            crop = crop.filter(ImageFilter.MedianFilter(3))
            debug_crop_path = f"debug/cell_{cell.get('row')}_{cell.get('col')}.png"
            crop.save(debug_crop_path)

            text = ''
            # Tesseract/pyocr path only
            ocr_tool_name = self.ocr_tool.get_name().lower() if self.ocr_tool else ""
            use_tess_configs = ("c-api" in ocr_tool_name or "libtesseract" in ocr_tool_name)
            builder = pyocr.builders.TextBuilder()
            builder.tesseract_layout = 11  # single line
            tess_vars = HANDWRITING_TESS_VARS.copy()
            tess_vars["tessedit_char_whitelist"] = "0123456789"
            if use_tess_configs:
                builder.tesseract_configs = [f"-c {k}={v}" for k, v in tess_vars.items()]
            with _handwriting_mode() if use_tess_configs else _null_context():
                text = self.ocr_tool.image_to_string(
                    crop,
                    lang="eng",
                    builder=builder
                )
            print(f"Tesseract row 0 cell (col {cell.get('col')}): raw='{text}'")
            text = re.sub(r"[^0-9]", "", text)
            results.append({"col": cell.get("col"), "text": text})
        return results
  
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
    
    
    # Récupère le nombre de pages d'un PDF
    def get_pdf_page_count(self, pdf_path):
        return len(fitz.open(pdf_path))

    # Récupère la mise en page d'un document
    def get_document_layout(self, image=None,
                            split_lines_to_words=False):
        """Run OCR on ``file_path`` and return a list of layout blocks.

        Args:
            file_path: Path to the image to OCR.
            mime_type: Unused, kept for backward compatibility.
            split_lines_to_words: When True, detected lines are exploded into
                individual word blocks (one block per word) using the word-level
                bounding boxes returned by Tesseract. When False (default), each
                line is emitted as a single ``paragraph`` block.
            handwriting: When True (default), runs Tesseract with the LSTM
                engine in "handwriting" mode (dictionaries disabled, no
                non-dict penalty, preserve spacing). Set False to fall back to
                the standard printed-text configuration.
        """
        try:
            _trace(f"get_document_layout: image opened size={image.size} mode={image.mode}")
            lang = "fra+eng"

            # Pass 1: line-level boxes (PSM 6)
            line_builder = pyocr.builders.LineBoxBuilder()
            line_builder.tesseract_layout = 6
            line_boxes = self.ocr_tool.image_to_string(image, lang=lang, builder=line_builder)

            _trace(f"get_document_layout: pass 1 done, {len(line_boxes)} line boxes")

            def pos_to_bbox(pos):
                return [
                    [pos[0][0], pos[0][1]],
                    [pos[1][0], pos[0][1]],
                    [pos[1][0], pos[1][1]],
                    [pos[0][0], pos[1][1]],
                ]

            block_vector = []

            if split_lines_to_words:
                # Pass 1b: word-level boxes (PSM 6) — split lines into individual words
                _trace("get_document_layout: pass 1b (WordBoxBuilder, PSM=6) start")
                wb_builder = pyocr.builders.WordBoxBuilder()
                wb_builder.tesseract_layout = 6
                word_boxes_psm6 = self.ocr_tool.image_to_string(image, lang=lang, builder=wb_builder)

                line_regions = []
                for line_box in line_boxes:
                    text = line_box.content.strip()
                    if not text:
                        continue
                    pos = line_box.position
                    line_regions.append(pos)
                    (lx1, ly1), (lx2, ly2) = pos
                    emitted = 0
                    for wb in word_boxes_psm6:
                        wtext = wb.content.strip()
                        if not wtext:
                            continue
                        wpos = wb.position
                        wcx = (wpos[0][0] + wpos[1][0]) / 2
                        wcy = (wpos[0][1] + wpos[1][1]) / 2
                        if lx1 <= wcx <= lx2 and ly1 <= wcy <= ly2:
                            block_vector.append({"page": 1, "text": wtext + "\n", "type": "word", "bounding_box": pos_to_bbox(wpos)})
                            emitted += 1
                    if emitted == 0:
                        block_vector.append({"page": 1, "text": text + "\n", "type": "paragraph", "bounding_box": pos_to_bbox(pos)})

                # Pass 2: sparse word boxes (PSM 11) — catch text outside line regions
                _trace("get_document_layout: pass 2 (WordBoxBuilder, PSM=11) start")
                wb_builder2 = pyocr.builders.WordBoxBuilder()
                wb_builder2.tesseract_layout = 11
                word_boxes_psm11 = self.ocr_tool.image_to_string(image, lang=lang, builder=wb_builder2)
                _trace(f"get_document_layout: pass 2 done, {len(word_boxes_psm11)} word boxes")
                for wb in word_boxes_psm11:
                    text = wb.content.strip()
                    if not text:
                        continue
                    pos = wb.position
                    wcx = (pos[0][0] + pos[1][0]) / 2
                    wcy = (pos[0][1] + pos[1][1]) / 2
                    if any(lr[0][0] <= wcx <= lr[1][0] and lr[0][1] <= wcy <= lr[1][1] for lr in line_regions):
                        continue
                    block_vector.append({"page": 1, "text": text + "\n", "type": "word", "bounding_box": pos_to_bbox(pos)})
            else:
                for line_box in line_boxes:
                    text = line_box.content.strip()
                    if not text:
                        continue
                    block_vector.append({"page": 1, "text": text + "\n", "type": "paragraph", "bounding_box": pos_to_bbox(line_box.position)})

            merged_blocks = self._merge_overlapping_blocks(block_vector)
            _trace(
                f"get_document_layout: returning {len(merged_blocks)} blocks "
                f"(merged from {len(block_vector)})"
            )
            return merged_blocks
        except Exception as e:
            import traceback
            _trace(f"get_document_layout: EXCEPTION: {e}")
            _trace(traceback.format_exc())
            return {"error": str(e)}
    
  # Extrait les tableaux d'un document
    def extract_tables(self, config_json_path, key_order, ocr_json_path, project_path,  pageid ):
        _trace(f"extract_tables: start pageid={pageid}")
        try:
            #Read config
            with open(config_json_path, "r", encoding="utf-8") as f:
                _raw = json.load(f).get(key_order, {})
                config_data = _raw.get("fields", _raw) if isinstance(_raw, dict) else _raw

            # target_text = [item["text"] for item in config_data if "text" in item]
            target_text = {param["label"]: param["text"] for param in config_data if "label" in param and "text" in param}
            target_parse = {param["label"]: param["parse"] for param in config_data if "label" in param and "parse" in param}
            # Load OCR layout data
            with open(ocr_json_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)

            # Guard against a failed get_document_layout pass (returns {"error": ...})
            if not isinstance(ocr_data, list):
                _trace(f"extract_tables: ocr_data not a list (type={type(ocr_data).__name__}), aborting pageid={pageid}")
                return {"error": "OCR layout unavailable"}

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

            # All OCR blocks (for debug display)
            all_blocks = []
            for block in ocr_data:
                if 'bounding_box' in block and 'text' in block:
                    all_blocks.append({
                        "text": block['text'].strip(),
                        "bbox": block['bounding_box']
                    })
            all_blocks_filename = f"all_blocks_{pageid}.json"
            all_blocks_path = os.path.join(project_path, all_blocks_filename)
            with open(all_blocks_path, "w", encoding="utf-8") as f:
                json.dump(all_blocks, f, indent=4, ensure_ascii=False)

            _trace(f"extract_tables: done pageid={pageid}")
            return {
                "label_bbox": label_bbox_ordered,
                "value_bbox": value_bbox_ordered,
                "extract_values": extract_values_ordered
            }

        except Exception as e:
            import traceback
            _trace(f"extract_tables: EXCEPTION: {e}")
            _trace(traceback.format_exc())
            return {"error": str(e)}
        
    def extract_tables_with_grid(self, config_json_path, key_order, grid_json_path, project_path, pageid):
        _trace(f"extract_tables_with_grid: start pageid={pageid} category={key_order}")
        try:
            #Read config (only the requested category, e.g. "interventions")
            with open(config_json_path, 'r', encoding='utf-8') as f:
                _raw = json.load(f).get(key_order, {})
                config_data = _raw.get("fields", _raw) if isinstance(_raw, dict) else _raw

            # target_text = [item["text"] for item in config_data if "text" in item]
            target_text = {param["label"]: param["text"] for param in config_data if "label" in param and "text" in param}
            
            # Load grid detection data
            with open(grid_json_path, 'r', encoding='utf-8') as f:
                grid_data = json.load(f)

             # Guard against an empty/invalid config section
            if not isinstance(config_data, list) or not config_data:
                _trace(f"extract_tables_with_grid: config section '{key_order}' empty/invalid, aborting pageid={pageid}")
                return {"error": f"Config category '{key_order}' unavailable"}

             # Guard against a failed grid detection pass (returns {"error": ...})
            if grid_data.get("error"):
                _trace(f"extract_tables_with_grid: grid_data error: {grid_data.get('error')}, aborting pageid={pageid}")
                return {"error": "Grid data unavailable"}

            # Load OCR layout and assign text to each grid cell (persists enriched grid).
            cells = self._assign_text_to_cells(grid_data, grid_json_path, project_path, pageid)

            # Load source page image (grayscale) so we can detect handwritten
            # marks in cells using pixel density instead of OCR text.
            gray_img = None
            for ext in ("png", "jpg", "jpeg"):
                candidate = os.path.join(project_path, f"{pageid}.{ext}")
                if os.path.exists(candidate):
                    try:
                        gray_img = Image.open(candidate).convert("L")
                    except Exception as e:
                        _trace(f"extract_tables_with_grid: could not open image {candidate}: {e}")
                    break


            # Match config labels to cells and derive bboxes + values.
            label_bbox_ordered, value_bbox_ordered, extract_values_ordered = \
                self._match_labels_to_cells(config_data, cells, gray_img=gray_img)

            # Set Phase, Visite, Date and Matricule values by OCRing row ""
            extract_values_ordered['Phase'] = None
            extract_values_ordered['Visite'] = None
            extract_values_ordered['Date'] = None
            extract_values_ordered["# Du Participant"] = None
            
            # OCR manuscript digits in row 0
            # row0_digits = self.read_row0_digits(cells, gray_img=gray_img)
            # with open(os.path.join(project_path, f"row0_digits_{pageid}.json"), "w", encoding="utf-8") as f:
            #     json.dump(row0_digits, f, indent=4, ensure_ascii=False)

            with open(os.path.join(project_path, f"label_bbox_{pageid}.json"), "w", encoding="utf-8") as f:
                json.dump(label_bbox_ordered, f, indent=4, ensure_ascii=False)
            with open(os.path.join(project_path, f"value_bbox_{pageid}.json"), "w", encoding="utf-8") as f:
                json.dump(value_bbox_ordered, f, indent=4, ensure_ascii=False)
            with open(os.path.join(project_path, f"table_{pageid}.json"), "w", encoding="utf-8") as f:
                json.dump(extract_values_ordered, f, indent=4, ensure_ascii=False)

            # All OCR blocks (for debug display in the frontend overlay).
            all_blocks = []
            ocr_json_path = os.path.join(project_path, f"output_{pageid}.json")
            if os.path.exists(ocr_json_path):
                try:
                    with open(ocr_json_path, 'r', encoding='utf-8') as f:
                        ocr_blocks = json.load(f)
                    if isinstance(ocr_blocks, list):
                        for block in ocr_blocks:
                            if 'bounding_box' in block and 'text' in block:
                                all_blocks.append({
                                    "text": block['text'].strip(),
                                    "bbox": block['bounding_box']
                                })
                except Exception as e:
                    _trace(f"extract_tables_with_grid: could not build all_blocks: {e}")
            with open(os.path.join(project_path, f"all_blocks_{pageid}.json"), "w", encoding="utf-8") as f:
                json.dump(all_blocks, f, indent=4, ensure_ascii=False)

            matched = sum(1 for v in label_bbox_ordered.values() if v is not None)
            _trace(f"extract_tables_with_grid: matched {matched}/{len(label_bbox_ordered)} labels for pageid={pageid}")
            return {
                "label_bbox": label_bbox_ordered,
                "value_bbox": value_bbox_ordered,
                "extract_values": extract_values_ordered
            }

        except Exception as e:
            import traceback
            _trace(f"extract_tables_with_grid: EXCEPTION: {e}")
            _trace(traceback.format_exc())
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Helpers for extract_tables_with_grid
    # ------------------------------------------------------------------
    def _assign_text_to_cells(self, grid_data, grid_json_path, project_path, pageid):
        """Load OCR layout (output_<pageid>.json) and attach a ``text`` field to
        each cell in ``grid_data`` based on which OCR blocks fall inside it.
        The enriched grid is written back to ``grid_json_path``.

        Returns the (mutated) list of cells.
        """
        ocr_json_path = os.path.join(project_path, f"output_{pageid}.json")
        ocr_blocks = []
        if os.path.exists(ocr_json_path):
            try:
                with open(ocr_json_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    ocr_blocks = loaded
            except Exception as e:
                _trace(f"_assign_text_to_cells: could not read OCR layout: {e}")

        cells = grid_data.get("cells", [])

        # Precompute block rectangles once for all cells.
        block_rects = []
        for block in ocr_blocks:
            brect = self._block_rect(block)
            if brect is None:
                continue
            block_rects.append((block, brect))

        # For each cell, collect all OCR texts that fit inside it.
        for cell in cells:
            cell["text"] = self._find_texts_in_cell(cell, block_rects)

        # Persist enriched grid (now includes "text" per cell) back to disk.
        with open(grid_json_path, "w", encoding="utf-8") as f:
            json.dump(grid_data, f, indent=4, ensure_ascii=False)

        return cells

    @staticmethod
    def _cell_rect(cell):
        bb = cell.get("bbox")
        if not bb or len(bb) < 3:
            return None
        xs = [pt[0] for pt in bb]
        ys = [pt[1] for pt in bb]
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _block_rect(block):
        bb = block.get("bounding_box")
        if not bb or len(bb) < 3:
            return None
        xs = [pt[0] for pt in bb]
        ys = [pt[1] for pt in bb]
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _merge_rect_to_bbox(rect):
        x1, y1, x2, y2 = rect
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    @staticmethod
    def _rect_intersection(a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        if ix2 <= ix1 or iy2 <= iy1:
            return 0
        return (ix2 - ix1) * (iy2 - iy1)

    @staticmethod
    def _rect_area(rect):
        x1, y1, x2, y2 = rect
        return max(0, x2 - x1) * max(0, y2 - y1)

    def _merge_overlapping_blocks(self, blocks, iou_threshold=0.6, contain_threshold=0.9):
        """Merge OCR blocks that likely represent the same content.

        Two blocks are merged when they overlap strongly (high IoU) or when one
        is mostly contained in the other. This removes duplicate bboxes that can
        appear across OCR passes.
        """
        if not blocks:
            return blocks

        groups = []
        for block in blocks:
            rect = self._block_rect(block)
            if rect is None:
                continue

            merged_into_group = False
            for group in groups:
                grect = group["rect"]
                inter = self._rect_intersection(rect, grect)
                if inter <= 0:
                    continue

                area_a = self._rect_area(rect)
                area_b = self._rect_area(grect)
                union = max(1, area_a + area_b - inter)
                iou = inter / union
                contain = inter / max(1, min(area_a, area_b))

                if iou >= iou_threshold or contain >= contain_threshold:
                    group["items"].append((block, rect))
                    group["rect"] = (
                        min(grect[0], rect[0]),
                        min(grect[1], rect[1]),
                        max(grect[2], rect[2]),
                        max(grect[3], rect[3]),
                    )
                    merged_into_group = True
                    break

            if not merged_into_group:
                groups.append({"rect": rect, "items": [(block, rect)]})

        merged_blocks = []
        for group in groups:
            items = group["items"]
            items.sort(key=lambda it: (it[1][1], it[1][0]))

            seen = set()
            text_parts = []
            for block, _ in items:
                raw = (block.get("text") or "").strip()
                if not raw:
                    continue
                key = raw.lower()
                if key in seen:
                    continue
                seen.add(key)
                text_parts.append(raw)

            merged_text = (" ".join(text_parts)).strip()
            block_type = "paragraph" if any((b.get("type") == "paragraph") for b, _ in items) else (items[0][0].get("type") or "word")
            page = items[0][0].get("page", 1)

            merged_blocks.append({
                "page": page,
                "text": (merged_text + "\n") if merged_text else "",
                "type": block_type,
                "bounding_box": self._merge_rect_to_bbox(group["rect"]),
            })

        return merged_blocks

    def _find_texts_in_cell(self, cell, block_rects):
        """Return the concatenated text of every OCR block whose bbox overlaps
        the cell's bbox (fully or partially). Each matching block contributes
        its full text; pieces are ordered top-to-bottom then left-to-right.

        ``block_rects`` is a precomputed list of ``(block, (x1, y1, x2, y2))``
        tuples produced from the OCR layout.
        """
        rect = self._cell_rect(cell)
        if not rect:
            return ""
        cx1, cy1, cx2, cy2 = rect

        pieces = []
        for block, (bx1, by1, bx2, by2) in block_rects:
            # Any (even partial) rectangle overlap between block and cell.
            if bx2 <= cx1 or bx1 >= cx2 or by2 <= cy1 or by1 >= cy2:
                continue

            text = (block.get("text") or "").strip()
            if not text:
                continue

            pieces.append((by1, bx1, text))

        pieces.sort(key=lambda m: (m[0], m[1]))
        return " ".join(t for _, _, t in pieces)

    def _cell_has_mark(self, cell, gray_img, dark_threshold=253, dark_ratio=125, inset=4):
        """Return True if the cell region in ``gray_img`` contains enough dark
        pixels to be considered a handwritten mark (check, tick, cross, ...).

        - Crops the cell bbox with a small ``inset`` to ignore the grid lines.
        - Counts pixels darker than ``dark_threshold`` via the image histogram.
        - Considers a cell marked if it contains at least ``dark_ratio`` dark pixels.
        """
        if gray_img is None:
            return False
        rect = self._cell_rect(cell)
        if not rect:
            return False
        x1, y1, x2, y2 = (int(round(v)) for v in rect)
        x1 += inset; y1 += inset; x2 -= inset; y2 -= inset
        if x2 <= x1 or y2 <= y1:
            return False
        img_w, img_h = gray_img.size
        x1 = max(0, min(x1, img_w)); x2 = max(0, min(x2, img_w))
        y1 = max(0, min(y1, img_h)); y2 = max(0, min(y2, img_h))
        if x2 <= x1 or y2 <= y1:
            return False
        crop = gray_img.crop((x1, y1, x2, y2))
        hist = crop.histogram()
        dark = sum(hist[:dark_threshold])
        total = (x2 - x1) * (y2 - y1)
        if total <= 0:
            return False
        # print ratio and debug info
        row = cell.get("row", "?")
        col = cell.get("col", "?")
        print(f"Cell dark: {dark}, total: {total} at row={row} col={col}")

        return dark   # threshold for "marked cell" can be adjusted based on testing

    def _match_labels_to_cells(self, config_data, cells, gray_img=None):
        """For each label in ``config_data``, find the cell whose text contains
        one of its target snippets and use that cell's text as both the label
        location and the extracted value.

        Returns three ordered dicts keyed by label:
        (label_bbox, value_bbox, extract_values).
        """
        from collections import OrderedDict

        def _norm(s):
            return (s or "").lower().strip()

        labels = [d['label'] for d in config_data if 'label' in d]
        label_bbox_ordered = OrderedDict((label, None) for label in labels)
        value_bbox_ordered = OrderedDict((label, None) for label in labels)
        extract_values_ordered = OrderedDict((label, None) for label in labels)

        # Build a (row, col) -> cell lookup for fast offset access.
        cells_by_rc = {}
        for c in cells:
            r = c.get("row")
            co = c.get("col")
            if r is None or co is None:
                continue
            cells_by_rc[(r, co)] = c

        def _parse_positions(raw_positions):
            """Parse entries into integer column offsets (number of columns to
            the right of the label cell). 0 means the label cell itself.
            Accepts ints (0, 1, 2, ...) or numeric strings ("0", "1", ...).
            Legacy 'r<n>' notation is still accepted. Invalid entries are
            skipped."""
            offsets = []
            for p in raw_positions or []:
                if isinstance(p, bool):
                    continue  # avoid True/False being treated as 1/0
                if isinstance(p, int):
                    if p >= 0:
                        offsets.append(p)
                    continue
                if isinstance(p, str):
                    s = p.strip()
                    if not s:
                        continue
                    m = re.match(r'^\s*r?\s*(\d+)\s*$', s, re.IGNORECASE)
                    if m:
                        offsets.append(int(m.group(1)))
            return offsets

        # Flatten config into (label, [snippets], [position offsets]) tuples.
        label_specs = []
        for param in config_data:
            label = param.get("label")
            if not label:
                continue
            snippets = [_norm(t) for t in param.get("text", []) if t]
            offsets = _parse_positions(param.get("parse"))
            if snippets:
                label_specs.append((label, snippets, offsets))

        # For each cell, search every config label's snippets in the cell text.
        # First matching label wins for that cell; first matching cell wins
        # for that label.
        for cell in cells:
            ct = _norm(cell.get("text", ""))
            if not ct:
                continue
            for label, snippets, offsets in label_specs:
                if label_bbox_ordered[label] is not None:
                    continue  # already matched a previous cell
                if any(snip in ct for snip in snippets):
                    bbox = cell.get("bbox")
                    label_bbox_ordered[label] = bbox

                    row = cell.get("row")
                    col = cell.get("col")
                    if not offsets or offsets[0] != 0:
                        # For each offset, get the number of dark pixels in the cell.
                        # Find the offset with the maximum dark pixel count, and set total to offset_weight of that offset (if >0), else 0.
                        offset_weight = {1: 1.0, 2: 0.5}
                        max_dark = 0
                        max_off = 0
                        value_bboxes = []
                        for off in offsets:
                            target = cells_by_rc.get((row, col + off))
                            value_bboxes.append(target.get("bbox") if target else None)
                            if target is not None :
                                dark = self._cell_has_mark(target, gray_img)
                                if isinstance(dark, (int, float)) and dark > max_dark:
                                    max_dark = dark
                                    max_off = off
                        total = offset_weight.get(max_off, 0) if max_dark > 0 else 0
                        extract_values_ordered[label] = f"{total:g}"
                        value_bbox_ordered[label] = value_bboxes
                    else:
                        # No positions configured: fall back to the label cell itself.
                        extract_values_ordered[label] = (cell.get("text") or "").strip()
                        value_bbox_ordered[label] = [cell.get("bbox")]
                    break

        return label_bbox_ordered, value_bbox_ordered, extract_values_ordered
                    
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
        if format_instructions and isinstance(format_instructions, str):
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
            fixed = apply_ocr_fixes(text or "")

            # Accept OCR noise between decimal separator and fractional part
            # (examples: "1,: 30", "2, 32", "4. ; 05").
            dec_match = re.search(r'(-?\d+)\s*[.,]\s*[^\d-]*\s*(\d+)', fixed)
            if dec_match:
                try:
                    num_str = f"{dec_match.group(1)}.{dec_match.group(2)}"
                    val = float(num_str)
                    return int(val) if val == int(val) else val
                except ValueError:
                    pass

            # Fallback: regular number extraction (decimal or integer).
            numbers = re.findall(r'-?\d+[.,]\d+|-?\d+', fixed)
            if numbers:
                try:
                    num_str = numbers[0].replace(',', '.')
                    val = float(num_str)
                    return int(val) if val == int(val) else val
                except ValueError:
                    pass
            return None

        def extract_digits_string(text):
            """Extract a string of 3-4 consecutive digits."""
            match = re.search(r'\d{3,4}', apply_ocr_fixes(text))
            return match.group(0) if match else None

        def _levenshtein_with_limit(a, b, max_dist=2):
            """Return edit distance if <= max_dist, else None (fast early stop)."""
            if abs(len(a) - len(b)) > max_dist:
                return None
            prev = list(range(len(b) + 1))
            for i, ca in enumerate(a, start=1):
                curr = [i]
                row_min = curr[0]
                for j, cb in enumerate(b, start=1):
                    cost = 0 if ca == cb else 1
                    curr.append(min(
                        prev[j] + 1,
                        curr[j - 1] + 1,
                        prev[j - 1] + cost,
                    ))
                    if curr[j] < row_min:
                        row_min = curr[j]
                if row_min > max_dist:
                    return None
                prev = curr
            return prev[-1] if prev[-1] <= max_dist else None

        def _find_fuzzy_span(haystack, needle, max_diff=2):
            """Return (start, end) best span for needle in haystack.

            Prefers exact regex match, then falls back to fuzzy match allowing
            up to ``max_diff`` edit operations.
            """
            m = re.search(re.escape(needle), haystack, re.IGNORECASE)
            if m:
                return m.start(), m.end()

            hs = haystack or ""
            nd = (needle or "").strip()
            if not hs or not nd:
                return None

            hs_l = hs.lower()
            nd_l = nd.lower()
            nlen = len(nd_l)
            min_len = max(1, nlen - max_diff)
            max_len = min(len(hs_l), nlen + max_diff)

            best = None  # (distance, start, end)
            for win_len in range(min_len, max_len + 1):
                for i in range(0, len(hs_l) - win_len + 1):
                    cand = hs_l[i:i + win_len]
                    dist = _levenshtein_with_limit(cand, nd_l, max_diff)
                    if dist is None:
                        continue
                    if best is None or dist < best[0]:
                        best = (dist, i, i + win_len)
                        if dist == 0:
                            return best[1], best[2]

            if best is None:
                return None
            return best[1], best[2]

        # First, try to extract the value from the label block itself
        # (e.g. "Cholestérol total 3,81 mmol/L" contains both label and value)
        label_block_text = label_block['text'].strip()
        # Find the label text(s) in the block and take what comes after
        search_targets = [label_text] if isinstance(label_text, str) else label_text
        for lt in search_targets:
            span = _find_fuzzy_span(label_block_text, lt, max_diff=2)
            if span:
                print(label_block_text)
                remainder = label_block_text[span[1]:]
                if remainder.strip():
                    inline_value = None
                    if parse_mode == "digits_string":
                        inline_value = extract_digits_string(remainder)
                    else:
                        inline_value = extract_number(remainder)
                        if inline_value is not None and allowed_values:
                            str_val = str(int(inline_value)) if isinstance(inline_value, (int, float)) and inline_value == int(inline_value) else str(inline_value)
                            if str_val not in allowed_values:
                                inline_value = extract_number(apply_ocr_fixes(remainder))
                                if inline_value is not None:
                                    str_val2 = str(int(inline_value)) if isinstance(inline_value, (int, float)) and inline_value == int(inline_value) else str(inline_value)
                                    if str_val2 not in allowed_values:
                                        inline_value = None
                    if inline_value is not None:
                        return {
                            'value': inline_value,
                            'value_bbox': label_block['bounding_box']
                        }
                    else: 
                        return {'value': None, 'value_bbox': None}
                # break

        # Score candidate blocks by spatial proximity
        # candidates = []
        # for i, block in enumerate(blocks):
        #     if i == label_idx:
        #         continue
        #     bbox = block['bounding_box']
        #     block_cx = (bbox[0][0] + bbox[1][0]) / 2
        #     block_cy = (bbox[0][1] + bbox[2][1]) / 2
        #     block_left = bbox[0][0]

        #     # Must be to the right of label or just below
        #     dy = block_cy - label_cy
        #     dx = block_left - label_right

        #     # Candidate: same line (within label_height tolerance) and to the right
        #     same_line = abs(dy) < label_height * 1.2 and dx > -20
        #     # Candidate: just below (within 2x label height) and roughly aligned
        #     just_below = 0 < dy < label_height * 3 and abs(block_left - label_bbox[0][0]) < label_height * 3

        #     if same_line or just_below:
        #         # Priority: same-line blocks first, then below; closer is better
        #         priority = 0 if same_line else 1
        #         distance = abs(dx) + abs(dy)
        #         candidates.append((priority, distance, i, block))

        # # Sort: same-line first, then by distance
        # candidates.sort(key=lambda c: (c[0], c[1]))

        # # Try to extract value from candidates
        # for _, _, _, block in candidates:
        #     text = block['text'].strip()
        #     if not text:
        #         continue

        #     value = None
        #     if parse_mode == "digits_string":
        #         value = extract_digits_string(text)
        #     else:
        #         value = extract_number(text)
        #         # If we got a number but there are allowed values, check
        #         if value is not None and allowed_values:
        #             if str(int(value) if isinstance(value, float) and value == int(value) else value) not in allowed_values:
        #                 # Apply OCR fixes and retry
        #                 value = extract_number(apply_ocr_fixes(text))

        #     if value is not None:
        #         # Handle allowed values constraint
        #         if allowed_values:
        #             str_val = str(int(value)) if isinstance(value, (int, float)) else str(value)
        #             if str_val not in allowed_values:
        #                 continue  # Skip, not in allowed set

        #         return {
        #             'value': value,
        #             'value_bbox': block['bounding_box']
        #         }

        # return {'value': None, 'value_bbox': None}

        return {'value': None, 'value_bbox': None}

    def find_matching_block(self, blocks, target):
        """
        Find a matching block by searching for target text(s).
        
        Args:
            blocks: List of OCR blocks
            target: Either a string or a list of strings to search for
            
        Returns:
            The first block that matches any of the target strings, or None if no match found
        """
        def _norm(s):
            return re.sub(r"\s+", " ", (s or "").lower()).strip()

        def _levenshtein_with_limit(a, b, max_dist=2):
            """Return edit distance if <= max_dist, else None (fast early stop)."""
            if abs(len(a) - len(b)) > max_dist:
                return None
            prev = list(range(len(b) + 1))
            for i, ca in enumerate(a, start=1):
                curr = [i]
                row_min = curr[0]
                for j, cb in enumerate(b, start=1):
                    cost = 0 if ca == cb else 1
                    curr.append(min(
                        prev[j] + 1,      # deletion
                        curr[j - 1] + 1,  # insertion
                        prev[j - 1] + cost  # substitution
                    ))
                    if curr[j] < row_min:
                        row_min = curr[j]
                if row_min > max_dist:
                    return None
                prev = curr
            return prev[-1] if prev[-1] <= max_dist else None

        # Convert single string to list for uniform processing
        targets = [target] if isinstance(target, str) else target

        # Pass 1: exact/regex contains match (existing behavior)
        for target_text in targets:
            if not target_text:
                continue
            pattern = re.compile(re.escape(target_text), re.IGNORECASE)
            for block in blocks:
                if pattern.search(block.get('text', '')):
                    return block

        # Pass 2: fuzzy partial match allowing 1-2 character differences
        max_diff = 2
        for target_text in targets:
            t = _norm(target_text)
            if not t:
                continue
            t_len = len(t)
            min_len = max(1, t_len - max_diff)

            for block in blocks:
                b = _norm(block.get('text', ''))
                if not b:
                    continue

                max_len = min(len(b), t_len + max_diff)

                # Compare target against every candidate substring in the block
                # with near-equal length so we tolerate OCR one/two-char noise.
                for win_len in range(min_len, max_len + 1):
                    for i in range(0, len(b) - win_len + 1):
                        candidate = b[i:i + win_len]
                        if _levenshtein_with_limit(candidate, t, max_diff) is not None:
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
            "Cholestérol total/C-HDL": "chol_hdlc",
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
            "Cholestérol-total/C-HDL": "chol_hdlc",
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
            "Cholestérol-total/C-HDL": "chol_hdlc",

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