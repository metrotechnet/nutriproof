// === GLOBAL STATE ===
let page_id = '';
let extract_values = {};
let raw_extract_values = {};
let label_bbox = {};
let value_bbox = {};
let all_blocks = [];
let grid_cells = [];
let field_visibility = {};
let field_text = {};
let field_type = {};
let field_parse = {};
let field_subsection = {};
let subsections = [];
let startPageIndex = null; // start_page initialized to page 1 (index 0)
let endPageIndex = null;
let docIndex = null;
let lastNewIncrementPageIndex = null;
let hasRenderedTableSection = false;
let autoSaveInFlight = false;
let autoSavePending = false;

let currentDocPage = 0;
let currentDocID = 0;
let currentProjectID = "";
let currentPageIndex = 1;
let currentFileList = [];
let currentCategory = null;

let nbrPageMax = 0;
let project_data = null;
let padding = 200; // ou la valeur désirée
let svg = null
let bboxOpacity = 0.2;

// Create different colors for each label with high contrast
const labelColors = {
  "Matricule": { label: `hsla(0, 85%, 45%,${bboxOpacity})`, value: `hsla(0, 85%, 65%,${bboxOpacity})` },
  "Visite": { label: `hsla(120, 85%, 35%,${bboxOpacity})`, value: `hsla(120, 85%, 55%,${bboxOpacity})` },
  "Temps": { label: `hsla(240, 85%, 45%,${bboxOpacity})`, value: `hsla(240, 85%, 65%,${bboxOpacity})` },
  "Protéine C réactive": { label: `hsla(300, 85%, 40%,${bboxOpacity})`, value: `hsla(300, 85%, 60%,${bboxOpacity})` },
  "Cholestérol": { label: `hsla(30, 90%, 40%,${bboxOpacity})`, value: `hsla(30, 90%, 60%,${bboxOpacity})` },
  "Triglycérides": { label: `hsla(180, 85%, 35%,${bboxOpacity})`, value: `hsla(180, 85%, 55%,${bboxOpacity})` },
  "Cholestérol-HDL": { label: `hsla(270, 85%, 45%,${bboxOpacity})`, value: `hsla(270, 85%, 65%,${bboxOpacity})` },
  "Cholestérol-LDL": { label: `hsla(60, 90%, 35%,${bboxOpacity})`, value: `hsla(60, 90%, 55%,${bboxOpacity})` },
  "Cholestérol non-HDL": { label: `hsla(330, 85%, 40%,${bboxOpacity})`, value: `hsla(330, 85%, 60%,${bboxOpacity})` },
  "Cholestérol total/C-HDL": { label: `hsla(150, 85%, 35%,${bboxOpacity})`, value: `hsla(150, 85%, 55%,${bboxOpacity})` },
  "Glucose": { label: `hsla(210, 85%, 45%,${bboxOpacity})`, value: `hsla(210, 85%, 65%,${bboxOpacity})` },
  "Insuline": { label: `hsla(45, 90%, 40%,${bboxOpacity})`, value: `hsla(45, 90%, 60%,${bboxOpacity})` }
};

const tooltip = document.createElement("div");
tooltip.className = "tooltip";
document.body.appendChild(tooltip);

// === DISPLAY INFO ===
/**
 * Updates the review header title area with contextual information.
 * @param {string} info - Text to show in the header.
 * @returns {void}
 */
function displayInfo(info) {
  //display info in ocr-demo-title
  const title = document.getElementById("ocr-demo-title");
  title.innerHTML = `${info}`;

}
// Démarrer un spinner avec sweetalert
/**
 * Shows a blocking loading modal with a spinner.
 * @param {string} message - Message displayed under the spinner.
 * @returns {void}
 */
function startSpinner(message) {
    Swal.fire({
        html: `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;">
                <div class="spinner-border text-primary" role="status" style="width:3rem;height:3rem;margin-bottom:1rem;"></div>
                <div>${message}</div>
            </div>`,
        showConfirmButton: false,
        allowOutsideClick: false,
        backdrop: true
    });
}
/**
 * Closes the loading modal if one is currently open.
 * @returns {void}
 */
function stopSpinner() {
    Swal.close();
}

// Fonction pour créer la liste des fichiers
/**
 * Builds the in-memory page index list for the selected document.
 * @param {string} project_id - Active project identifier.
 * @param {string} document_id - Active document identifier.
 * @param {Array<object>} fileArray - Project document metadata array.
 * @returns {void}
 */
function createFileList(project_id, document_id, fileArray) {
  //loop in fileArray and add each file with its page number
  currentFileList.push({ document_id: 0, page: 0 });
  fileArray.forEach((file, index) => {
    // create a list on nbr_pages of document id in fileIndexList
    if (file.document_id==document_id) {
      for (let i = 0; i < file.nbr_pages; i++) {
          currentFileList.push({ document_id: file.document_id, page: i + 1 });
        }
        nbrPageMax += file.nbr_pages;
    }
  });
  currentProjectID = project_id;
}


// === MAIN LOADING FUNCTION ===
/**
 * Loads all page assets (table data, OCR data, bboxes, debug overlays) then renders the page.
 * @param {string} project_id - Active project identifier.
 * @param {number} index - 1-based logical page index used by backend filenames.
 * @param {boolean} [init_scroll=false] - Whether to reset image viewer scroll position.
 * @param {"raw"|"edited"} [sourceMode="edited"] - Source mode for table payload.
 * @param {boolean} [loadIndexes=true] - Whether to hydrate start/end/doc indices from loaded JSON data.
 * @param {boolean} [renderTable=true] - Whether to rebuild/refresh the table section after image render.
 * @returns {Promise<boolean|undefined>} True when page data is loaded; false/undefined otherwise.
 */
async function loadPage(project_id, index, init_scroll=false, sourceMode="edited", loadIndexes=true, renderTable=true) {
  
  if (currentFileList.length === 0 || index <= 0 || index > nbrPageMax) {
    console.error("No files available for loading.");
    return;
  }
  try {

    currentPageIndex = index;
    currentDocPage = currentFileList[index].page;
    currentDocID = currentFileList[index].document_id;
    currentCategory = project_data?.find(f => f.document_id === currentDocID)?.category ?? null;
    //start spinner cursor
    page_id = `page_${index}`;
    const responses = await Promise.all([
        fetch(`/get_data/${project_id}/${currentDocID}/label_bbox_${page_id}.json?source=${encodeURIComponent(sourceMode)}`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/value_bbox_${page_id}.json?source=${encodeURIComponent(sourceMode)}`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/table_${page_id}.json?source=${encodeURIComponent(sourceMode)}`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/table_${page_id}.json?source=raw`).then(res => res.json()).catch(() => ({})),
        fetch(`/get_raw_data/${project_id}/${currentDocID}/all_blocks_${page_id}.json`).then(res => res.json()).catch(() => []),
        fetch(`/get_raw_data/${project_id}/${currentDocID}/grid_${page_id}.json`).then(res => res.json()).catch(() => ({}))
    ]);
    if (!responses[0].data_string || !responses[1].data_string || !responses[2].data_string) {
        // Handle empty responses
      return false;
    }
    label_bbox = JSON.parse(responses[0].data_string || '{}');
    value_bbox = JSON.parse(responses[1].data_string || '{}');
    extract_values = JSON.parse(responses[2].data_string || '{}');
    raw_extract_values = JSON.parse(responses[3]?.data_string || '{}');
    // console.log("Raw extract values:", raw_extract_values);
    if (loadIndexes) {
      startPageIndex = parseNullableIndex(extract_values.start_index);
      endPageIndex = parseNullableIndex(extract_values.end_index);
      docIndex = parseNullableIndex(extract_values.doc_index);
    }

    field_visibility = responses[2].field_visibility || {};
    field_text = responses[2].field_text || {};
    field_type = responses[2].field_type || {};
    field_parse = responses[2].field_parse || {};
    field_subsection = responses[2].field_subsection || {};
    subsections = responses[2].subsections || [];
    all_blocks = responses[4] || [];
    const gridData = responses[5] || {};
    grid_cells = gridData.cells || [];
    updateRangeIndexDisplay();

    return await displayPage(project_id, currentDocID, index, init_scroll, false, renderTable);
  } catch (error) {
    console.error("Erreur chargement des données OCR:", error);
    return false;
  }
}

// === DISPLAY IMAGE & BBOXES ===
/**
 * Renders the page image, overlays and editable table for a given page index.
 * @param {string} project_id - Active project identifier.
 * @param {string} document_id - Active document identifier.
 * @param {number} index - 1-based logical page index.
 * @param {boolean} [init_scroll=false] - Whether to re-center scroll on first render.
 * @param {boolean} [imageOnly=false] - If true, updates only image/overlays without rebuilding table UI.
 * @param {boolean} [renderTable=true] - If false, keeps existing table content/controls unchanged.
 * @returns {Promise<boolean>} True when rendering completed, false on load/render failure.
 */
async function displayPage(project_id, document_id, index, init_scroll=false, imageOnly=false, renderTable=true) {

  return await new Promise((resolve) => {
    let settled = false;
    const finish = (ok) => {
      if (settled) return;
      settled = true;
      resolve(ok);
    };

    // Cherche l'image
    const imageElement = document.getElementById("page-image");
    imageElement.style.display = "none";
    if(svg!=null)
      svg.style.display = "none"; // Masquer au départ

    page_id = `page_${index}`;

    imageElement.onload = () => {
      //remove polygons and svg
      document.querySelectorAll('svg.bbox').forEach(el => el.remove());
      document.querySelectorAll('svg').forEach(el => el.remove());

      const imageElement = document.getElementById("page-image");
      const viewerImage = document.getElementById("viewer-image");
      imageElement.style.display = "block";

    // Utilise la taille affichée de l'image
      const imgWidth = imageElement.clientWidth;
      const imgHeight = imageElement.naturalHeight * imageElement.clientWidth / imageElement.naturalWidth;

      // Dimensions effectives après rotation
      const isRotated = (currentRotation % 180 !== 0);
      const effectiveWidth = isRotated ? imgHeight : imgWidth;
      const effectiveHeight = isRotated ? imgWidth : imgHeight;
      const viewerWidth = effectiveWidth * currentScale + padding * 2;
      const viewerHeight = effectiveHeight * currentScale + padding * 2;

      // Centre de rotation = centre de l'image
      const cx = imgWidth / 2;
      const cy = imgHeight / 2;
      const transformOrigin = `${cx}px ${cy}px`;

      // Position de l'image: le centre doit être au centre du viewer
      const imgLeft = padding + (effectiveWidth * currentScale - imgWidth) / 2;
      const imgTop = padding + (effectiveHeight * currentScale - imgHeight) / 2;

      //display img size to console
      // console.log(`Image size: ${imgWidth}px x ${imgHeight}px`);
      // console.log(`Scale: ${currentScale}, Rotation: ${currentRotation}`);
      // Ajoute un padding autour pour le scroll
    // Le SVG aura la même taille que l'image + padding
      svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.style.left = `${imgLeft}px`;
      svg.style.top = `${imgTop}px`;
      svg.style.width = `${imgWidth}px`;
      svg.style.height = `${imgHeight}px`;
      // svg.style.backgroundColor = "rgba(255, 0, 0, 0.3)";
      svg.style.pointerEvents = "auto";
      svg.style.position = "absolute";
      svg.style.transformOrigin = transformOrigin;

      // Calcule le scale pour les bboxes
      const scaleX =  imgWidth / imageElement.naturalWidth;
      const scaleY =  imgHeight / imageElement.naturalHeight;
      if (!imageOnly) {
        // Affichage des polygones avec couleurs par label
        displayAllBlocks(svg, all_blocks, 0, 0, scaleX, scaleY);

        displayAllGridCells(svg, grid_cells, 0, 0, scaleX, scaleY);

        displayBbox(svg, extract_values, value_bbox, 0, 0, scaleX, scaleY, "value");

        updateRangeIndexDisplay();


      }

      // Applique la transformation
      svg.style.transform = `rotate(${currentRotation}deg) scale(${currentScale})`;

      // Applique la transformation au conteneur de l'image
      imageElement.style.width = `${imgWidth}px`;
      imageElement.style.height = `${imgHeight}px`;
      imageElement.style.position = "absolute";
      imageElement.style.left = `${imgLeft}px`;
      imageElement.style.top = `${imgTop}px`;
      imageElement.style.transformOrigin = transformOrigin;
      imageElement.style.transform = `rotate(${currentRotation}deg) scale(${currentScale})`;

      // // viewerImage.style.backgroundColor = "rgba(0, 255, 0, 0.3)";
      viewerImage.style.width = viewerWidth + "px";
      viewerImage.style.height = viewerHeight + "px";

      // Initialiser le défilement
      if(init_scroll) {
        const viewerImageFrame = document.getElementById("viewer-image-frame");
        //Scroll viewerImage to center
        viewerImageFrame.scrollLeft = padding;
        viewerImageFrame.scrollTop = padding;
      }
      //Add SVG  elements
      svg.style.display = "block";
      viewerImage.appendChild(svg);  

      if (renderTable) {
        renderTableSection(imageOnly);
      } else {
        updatePaginationControls(currentPageIndex, nbrPageMax);
        updateRangeIndexDisplay();
      }
      finish(true);
    };
    imageElement.onerror = () => {
      imageElement.style.display = "none";
      // Optionnel: afficher un message d’erreur
      finish(false);
    };

    // Load image
    fetch(`/get_image/${project_id}/${document_id}/${page_id}.png`)
      .then(res => res.blob())
      .then(blob => {
        imageElement.src = URL.createObjectURL(blob);
      })
      .catch(err => {
        console.error("Image load failed:", err);
        imageElement.style.display = "none";
        finish(false);
      });
  });
}

/**
 * Renders (or refreshes) the table, actions and pagination section separately from image drawing.
 * @param {boolean} imageOnly - When true, only syncs pagination input without rebuilding the table.
 * @returns {void}
 */
function renderTableSection(imageOnly) {
  if (!imageOnly) {
    // Effacer le tableau/pagination sans retirer la structure des slots
    const tableValuesContainer = document.getElementById("table-values-container");
    const paginationSlot = document.getElementById("pagination-slot");
    const tableHeaderSlot = document.getElementById("table-header-slot");
    if (tableValuesContainer) tableValuesContainer.innerHTML = "";
    if (paginationSlot) paginationSlot.innerHTML = "";
    if (tableHeaderSlot) tableHeaderSlot.innerHTML = "";
    // Keep parameter table order aligned with JSON definition order.
    // 1) keys order from label_bbox (built from config JSON order on backend)
    // 2) append any remaining keys in their existing insertion order
    const labelOrder = Object.keys(label_bbox || {});
    const entries = Object.entries(extract_values || {});

    const normalizeKey = (s) =>
      String(s || "")
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[-_/]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

    // Keep both exact and normalized views so keys like
    // "Cholestérol-LDL" and "Cholestérol LDL" map to same slot.
    const byKey = new Map(entries);
    const byNorm = new Map();
    for (const [k, v] of entries) {
      const nk = normalizeKey(k);
      if (!byNorm.has(nk)) byNorm.set(nk, [k, v]);
    }
    const orderedEntries = [];

    for (const key of labelOrder) {
      if (byKey.has(key)) {
        orderedEntries.push([key, byKey.get(key)]);
        byKey.delete(key);
        const nk = normalizeKey(key);
        if (byNorm.has(nk) && byNorm.get(nk)[0] === key) {
          byNorm.delete(nk);
        }
      } else {
        const nk = normalizeKey(key);
        if (byNorm.has(nk)) {
          const [realKey, value] = byNorm.get(nk);
          orderedEntries.push([realKey, value]);
          byNorm.delete(nk);
          byKey.delete(realKey);
        }
      }
    }

    for (const [key, value] of entries) {
      if (byKey.has(key)) {
        orderedEntries.push([key, value]);
        byKey.delete(key);
      }
    }
    const metadataEntries = orderedEntries.filter(([key]) =>
      ["start_index", "end_index", "doc_index"].includes(key)
    );
    const contentEntries = orderedEntries.filter(([key]) =>
      !["start_index", "end_index", "doc_index"].includes(key)
    );

    const hiddenEntries = [];
    const groupBuckets = new Map();
    contentEntries.forEach(([key, value], indexInOrder) => {
      if (field_visibility[key] === false) {
        hiddenEntries.push([key, value]);
        return;
      }
      const groupId = field_subsection[key] || "__ungrouped__";
      if (!groupBuckets.has(groupId)) {
        groupBuckets.set(groupId, {
          groupId,
          entries: [],
          filledCount: 0,
          firstIndex: indexInOrder
        });
      }
      const bucket = groupBuckets.get(groupId);
      bucket.entries.push([key, value]);
      if (!isEmptyValue(value)) bucket.filledCount += 1;
    });

    const subsectionLabelById = {};
    if (Array.isArray(subsections)) {
      subsections.forEach(section => {
        if (section && section.id) {
          subsectionLabelById[section.id] = section.label || section.id;
        }
      });
    }

    const normalizedInfoTokens = ["info", "informations", "information"];
    const isInfoGroup = (groupId) => {
      const normalizedId = normalizeKey(groupId);
      const normalizedLabel = normalizeKey(subsectionLabelById[groupId] || "");
      return normalizedInfoTokens.some(token =>
        normalizedId.includes(token) || normalizedLabel.includes(token)
      );
    };

    const sortedGroups = Array.from(groupBuckets.values()).sort((a, b) => {
      const aIsInfo = isInfoGroup(a.groupId);
      const bIsInfo = isInfoGroup(b.groupId);
      if (aIsInfo !== bIsInfo) return aIsInfo ? -1 : 1;
      if (b.filledCount !== a.filledCount) return b.filledCount - a.filledCount;
      return a.firstIndex - b.firstIndex;
    });

    const reorderedContentEntries = sortedGroups.flatMap(group => group.entries);
    extract_values = Object.fromEntries([...reorderedContentEntries, ...hiddenEntries, ...metadataEntries]);

    // Header actions (Nouveau / Prochaine)
    createTopActionControls();
    updateRangeIndexDisplay();

    // Génération du tableau éditable
    generateEditableTable(extract_values);
    // Pagination après le tableau
    createPaginationControls(currentPageIndex, nbrPageMax);
    return;
  }

  const pageInput = document.getElementById("page-index-input");
  if (pageInput) {
    pageInput.value = String(currentPageIndex);
  }
}

/**
 * Updates existing table rows with values from the loaded page without recreating controls.
 * @param {Object} data - Current page value map.
 * @returns {void}
 */
function updateExistingTableValues(data) {
  const table = document.querySelector(".param-table");
  if (!table) return;

  table.querySelectorAll("tbody tr").forEach(row => {
    if (row.classList.contains("group-separator-row")) return;
    const keyCell = row.querySelector("td.param-cell");
    const valueCell = row.querySelector("td.value-cell");
    if (!keyCell || !valueCell) return;

    const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
    if (!key || ["start_index", "end_index", "doc_index"].includes(key)) return;
    const nextValue = data[key];
    valueCell.textContent = nextValue !== null && nextValue !== undefined ? String(nextValue) : "";
  });
}

// === DISPLAY ALL TESSERACT BLOCKS ===
/**
 * Draws OCR text block rectangles on the SVG overlay.
 * @param {SVGElement} svg - Target SVG overlay.
 * @param {Array<object>} blocks - OCR block list with bbox/text fields.
 * @param {number} offsetX - Horizontal pixel offset.
 * @param {number} offsetY - Vertical pixel offset.
 * @param {number} scaleX - Horizontal scaling factor.
 * @param {number} scaleY - Vertical scaling factor.
 * @returns {void}
 */
function displayAllBlocks(svg, blocks, offsetX, offsetY, scaleX, scaleY) {
  if (!blocks || !blocks.length) return;
  blocks.forEach((block) => {
    const bbox = block.bbox;
    if (!bbox || bbox.length !== 4) return;
    let x = bbox[0][0] * scaleX + offsetX;
    let y = bbox[0][1] * scaleY + offsetY;
    let w = Math.max(1, (bbox[1][0] - bbox[0][0]) * scaleX);
    let h = Math.max(1, (bbox[2][1] - bbox[1][1]) * scaleY);

    let rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", x);
    rect.setAttribute("y", y);
    rect.setAttribute("width", w);
    rect.setAttribute("height", h);
    rect.setAttribute("fill", "none");
    rect.setAttribute("stroke", "rgba(100, 100, 255, 0.5)");
    rect.setAttribute("stroke-width", "1");

    rect.addEventListener("mouseenter", (e) => {
      tooltip.textContent = block.text;
      tooltip.style.opacity = 1;
    });
    rect.addEventListener("mousemove", (e) => {
      tooltip.style.left = `${e.pageX + 10}px`;
      tooltip.style.top = `${e.pageY + 10}px`;
    });
    rect.addEventListener("mouseleave", () => {
      tooltip.style.opacity = 0;
    });

    svg.appendChild(rect);
  });
}

/**
 * Persists current table data and propagates it to every page in the active range.
 * @param {Object|null} [dataOverride=null] - Optional payload overriding table collection.
 * @returns {Promise<void>}
 */
async function autoSaveInputAndBackfill(dataOverride = null) {
  const data = dataOverride || collectTableDataForSave();
  if (!data) return;

  const finalData = withStartEndMetadata(data);
  const startIndex = parseNullableIndex(startPageIndex);
  const endIndex = parseNullableIndex(endPageIndex);
  if (!Number.isInteger(startIndex) || !Number.isInteger(endIndex)) {
    return;
  }

  console.log("Auto-saving from page", startIndex, "to", endIndex);
  for (let i = startIndex; i <= endIndex; i++) {
    await saveTableDataToPageIndex(i, finalData);
  }
}

/**
 * Debounces autosave requests so concurrent keystrokes are serialized safely.
 * @returns {void}
 */
function scheduleAutoSaveFromInput() {
  autoSavePending = true;
  if (autoSaveInFlight) return;

  const run = async () => {
  if (!autoSavePending) return;
  autoSavePending = false;
  autoSaveInFlight = true;
  try {
    await autoSaveInputAndBackfill();
  } catch (err) {
    console.error("Auto-save failed:", err);
  } finally {
    autoSaveInFlight = false;
    if (autoSavePending) {
      run();
    }
  }
  };

  run();
}

// === DISPLAY BOXES ON IMAGE ===
/**
 * Draws label/value polygons on the SVG overlay and configures hover tooltips.
 * @param {SVGElement} svg - Target SVG overlay.
 * @param {Object} data - Current value map (used for tooltip values).
 * @param {Object} boxes - Bounding box map keyed by label.
 * @param {number} offsetX - Horizontal pixel offset.
 * @param {number} offsetY - Vertical pixel offset.
 * @param {number} scaleX - Horizontal scaling factor.
 * @param {number} scaleY - Vertical scaling factor.
 * @param {"label"|"value"} boxType - Overlay type to style.
 * @returns {void}
 */
function displayBbox(svg, data, boxes, offsetX,offsetY, scaleX, scaleY, boxType) {

  Object.entries(boxes).forEach(([label, bbox]) => {
    if (!bbox) return;

    // value_bbox may be either a single 4-point polygon (legacy) or an array
    // of polygons (when the config has `positions: ["r1","r2",...]` and one
    // target cell is extracted per offset). Normalize to a list of (bbox, value)
    // pairs so the same rendering code handles both shapes.
    const isListOfBoxes = Array.isArray(bbox[0]) && Array.isArray(bbox[0][0]);
    const value = data[label];
    let pairs;
    if (isListOfBoxes) {
      pairs = bbox.map((bb, i) => {
        const v = Array.isArray(value) ? value[i] : value;
        return { bbox: bb, value: v, index: i };
      });
    } else {
      pairs = [{ bbox: bbox, value: value, index: null }];
    }

    pairs.forEach(({ bbox: bb, value: v, index }) => {
      if (!bb || bb.length !== 4) return;
      let x = bb[0][0] * scaleX + offsetX;
      let y = bb[0][1] * scaleY + offsetY;
      let w = Math.max(1, (bb[1][0] - bb[0][0]) * scaleX);
      let h = Math.max(1, (bb[2][1] - bb[1][1]) * scaleY);

      let corners = [
        [x, y],
        [x + w, y],
        [x + w, y + h],
        [x, y + h]
      ];

      let polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      polygon.setAttribute("points", corners.map(([px, py]) => `${px},${py}`).join(" "));
      polygon.setAttribute("class", "bbox");

      // Default fill; for "target" polygons (value bboxes coming from a
      // positions array) use a distinct semi-transparent highlight so they
      // stand out from regular label/value boxes.
      let fillColor = "rgba(80, 160, 255, 0.18)";
      let strokeColor = "none";
      let strokeWidth = 0;
      if (isListOfBoxes && boxType === "value") {
        fillColor = "rgba(255, 215, 0, 0.25)";   // gold tint
        strokeColor = "rgba(255, 140, 0, 0.9)";   // orange outline
        strokeWidth = 1.5;
      } else if (currentCategory.startsWith('bilan_lipidique_') && labelColors[label] && labelColors[label][boxType]) {
        fillColor = labelColors[label][boxType];
      }

      polygon.setAttribute("fill", fillColor);
      polygon.setAttribute("stroke", strokeColor);
      polygon.setAttribute("stroke-width", strokeWidth);
      polygon.setAttribute("title", label);

      const tooltipText = index !== null
        ? `${label}[${index}] = ${v ?? ""}`
        : `${label} = ${v ?? ""}`;
      // console.log(`Applying color for "${label}": ${tooltipText}`);

      polygon.addEventListener("mouseenter", () => {
        tooltip.textContent = tooltipText;
        tooltip.style.opacity = 1;
      });
      polygon.addEventListener("mousemove", (e) => {
        tooltip.style.left = `${e.pageX + 10}px`;
        tooltip.style.top = `${e.pageY + 10}px`;
      });
      polygon.addEventListener("mouseleave", () => {
        tooltip.style.opacity = 0;
      });

      svg.appendChild(polygon);
    });
  });

}

// === DISPLAY ALL GRID CELLS ===
/**
 * Draws detected grid cell contours used for manual OCR debugging.
 * @param {SVGElement} svg - Target SVG overlay.
 * @param {Array<object>} gridCells - Grid cell list with row/col/bbox metadata.
 * @param {number} offsetX - Horizontal pixel offset.
 * @param {number} offsetY - Vertical pixel offset.
 * @param {number} scaleX - Horizontal scaling factor.
 * @param {number} scaleY - Vertical scaling factor.
 * @returns {void}
 */
function displayAllGridCells(svg, gridCells, offsetX, offsetY, scaleX, scaleY) {
  if (!gridCells || !gridCells.length) return;

  // Palette of 12 distinct row outline colors (matches Python row_colors).
  const rowColors = [
    "#3cb44b", "#e6194b", "#0082c8", "#f58330",
    "#911eb4", "#46f0f0", "#f032e6", "#d2f53c",
    "#fabebe", "#008080", "#dcbeff", "#aa6e28",
  ];

  // Seeded pseudo-random fill colors per cell (same seed as Python rng=42).
  function cellFill(index) {
    // Simple LCG so colors are stable across reloads.
    let s = (index * 1664525 + 1013904223 + 42) >>> 0;
    const r = 80 + (s & 0x7f);
    s = (s * 1664525 + 1013904223) >>> 0;
    const g = 80 + (s & 0x7f);
    s = (s * 1664525 + 1013904223) >>> 0;
    const b = 80 + (s & 0x7f);
    return `rgba(${r},${g},${b},0.12)`;
  }

  // Two-pass rendering: filled rectangles first, then outlines + labels on top
  // (mirrors the Python debug image so contours stay crisp over fills).
  const geometries = [];
  gridCells.forEach((cell, idx) => {
    const bbox = cell.bbox;
    if (!bbox || bbox.length !== 4) return;

    const x = bbox[0][0] * scaleX + offsetX;
    const y = bbox[0][1] * scaleY + offsetY;
    const w = Math.max(1, (bbox[1][0] - bbox[0][0]) * scaleX);
    const h = Math.max(1, (bbox[2][1] - bbox[1][1]) * scaleY);
    const rowIdx = cell.row ?? 0;
    const outlineColor = rowColors[rowIdx % rowColors.length];
    const fillColor = cellFill(idx);

    geometries.push({ cell, x, y, w, h, outlineColor, fillColor });
  });

  // Pass 1: filled rectangles.
  // geometries.forEach(({ x, y, w, h, fillColor }) => {
  //   const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  //   rect.setAttribute("x", x);
  //   rect.setAttribute("y", y);
  //   rect.setAttribute("width", w);
  //   rect.setAttribute("height", h);
  //   rect.setAttribute("fill", fillColor);
  //   rect.setAttribute("stroke", "none");
  //   svg.appendChild(rect);
  // });

  // Pass 2: outlines, labels, hover interactions.
  geometries.forEach(({ cell, x, y, w, h, outlineColor }) => {
    const contour = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    contour.setAttribute("x", x);
    contour.setAttribute("y", y);
    contour.setAttribute("width", w);
    contour.setAttribute("height", h);
    contour.setAttribute("fill", "transparent");
    contour.setAttribute("stroke", outlineColor);
    contour.setAttribute("stroke-width", "2");
    contour.style.pointerEvents = "auto";

    contour.addEventListener("mouseenter", () => {
      const row = (cell.row ?? "?");
      const col = (cell.col ?? "?");
      //display bbox w and h in tooltip
      const w = Math.round((cell.bbox[1][0] - cell.bbox[0][0]) * scaleX);
      const h = Math.round((cell.bbox[2][1] - cell.bbox[1][1]) * scaleY);
      tooltip.textContent = `Grille r${row ?? "?"} c${col ?? "?"} (${w}x${h}px)`;
      tooltip.style.opacity = 1;
    });
    contour.addEventListener("mousemove", (e) => {
      tooltip.style.left = `${e.pageX + 10}px`;
      tooltip.style.top = `${e.pageY + 10}px`;
    });
    contour.addEventListener("mouseleave", () => {
      tooltip.style.opacity = 0;
    });

    svg.appendChild(contour);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", x + 3);
    label.setAttribute("y", y + 12);
    label.setAttribute("font-family", "Arial, sans-serif");
    label.setAttribute("font-size", "10");
    label.setAttribute("fill", outlineColor);
    label.setAttribute("pointer-events", "none");
    label.textContent = `r${cell.row ?? "?"}c${cell.col ?? "?"}`;
    svg.appendChild(label);
  });
}

// === PAGINATION ===
/**
 * Builds top action controls (Nouveau/Prochaine) and index display container.
 * @returns {void}
 */
function createTopActionControls() {
  const slot = document.getElementById("table-header-slot");
  if (!slot) return;

  const row = document.createElement("div");
  row.className = "table-header-actions";
  const instructions = document.createElement("div");
  instructions.className = "table-header-actions-instructions";
  const instructionLine1 = document.createElement("div");
  instructionLine1.innerHTML = "<strong>Étape 1 :</strong> cliquez sur « Début » pour démarrer une nouvelle saisie d'un document.";
  const instructionLine2 = document.createElement("div");
  instructionLine2.innerHTML = "<strong>Étape 2 :</strong> cliquez sur « Copier » pour aller à la page suivante en gardant les valeurs déjà remplies.";
  const instructionLine3 = document.createElement("div");
  instructionLine3.innerHTML = "<strong>Note :</strong> les valeurs détectées par l'OCR seront également ajoutées automatiquement dans les champs vides.";
  instructions.append(instructionLine1, instructionLine2, instructionLine3);
  const buttons = document.createElement("div");
  buttons.className = "table-header-actions-buttons";

  const newBtn = document.createElement("button");
  newBtn.id = "new-data-btn";
  newBtn.type = "button";
  newBtn.className = "btn btn-outline-primary btn-sm save-table-btn";
  newBtn.textContent = "Début";
  newBtn.onclick = startNewRangeFromRaw;

  const prochaineBtn = document.createElement("button");
  prochaineBtn.id = "next-workflow-btn";
  prochaineBtn.type = "button";
  prochaineBtn.className = "btn btn-outline-primary btn-sm save-table-btn";
  prochaineBtn.textContent = "Copier";
  prochaineBtn.onclick = nextPageWithLoadAndPropagate;

  buttons.append(newBtn, prochaineBtn);

  const rangeInfo = document.createElement("div");
  rangeInfo.id = "range-index-display";
  rangeInfo.className = "range-index-display";

  const controlsRow = document.createElement("div");
  controlsRow.className = "table-header-controls-row";
  controlsRow.append(buttons, rangeInfo);

  row.append(instructions, controlsRow);
  slot.appendChild(row);
}

/**
 * Refreshes header metadata display for document/range indices.
 * @returns {void}
 */
function updateRangeIndexDisplay() {
  const rangeInfo = document.getElementById("range-index-display");
  if (!rangeInfo) return;

  const rawStart = Number.isInteger(startPageIndex)
    ? startPageIndex
    : parseNullableIndex(extract_values?.start_index);
  const rawEnd = Number.isInteger(endPageIndex)
    ? endPageIndex
    : parseNullableIndex(extract_values?.end_index);
  const rawDocIndex = Number.isInteger(docIndex)
    ? docIndex
    : parseNullableIndex(extract_values?.doc_index);

  const startText = Number.isInteger(rawStart) ? String(rawStart) : "-";
  const endText = Number.isInteger(rawEnd) ? String(rawEnd) : "-";
  const docText = Number.isInteger(rawDocIndex) ? String(rawDocIndex) : "-";
  rangeInfo.textContent = `Document: ${docText} | Début: ${startText} | Fin: ${endText}`;
} 

/**
 * Creates footer pagination controls and page number input.
 * @param {number} current - Current 1-based page shown in UI.
 * @param {number} max - Maximum available page count.
 * @returns {void}
 */
function createPaginationControls(current, max) {
  const container = document.createElement("div");
  container.className = "pagination-container";

  const prevBtn = document.createElement("button");
  prevBtn.id = "page-prev-btn";
  prevBtn.type = "button";
  prevBtn.className = "btn btn-outline-primary btn-sm mx-1";
  prevBtn.innerHTML = '<i class="bi bi-chevron-left"></i> ';
  prevBtn.onclick = previousPage;

  const pageDiv = document.createElement("div");
  const pageText = document.createElement("span");
  pageText.textContent = `Page:`;
  pageText.id = "page-display";

  // Ajout de l'input pour sélectionner la page
  const pageInput = document.createElement("input");
  pageInput.id = "page-index-input";
  pageInput.type = "number";
  pageInput.min = 1;
  pageInput.max = max;
  pageInput.value = current;
  pageInput.style.width = "60px";
  pageInput.style.margin = "0 4px";
  //add event when user pres enter
  pageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      let val = parseInt(pageInput.value);
      if (!isNaN(val) && val >= 1 && val <= max) {
        navigateToPageWithMode(val - 1);
      } else {
        pageInput.value = current;
      }
    }
  });
  //Add event when user change input
  pageInput.addEventListener("change", () => {
    let val = parseInt(pageInput.value);
    if (!isNaN(val) && val >= 1 && val <= max) {
      navigateToPageWithMode(val - 1);
    } else {
      pageInput.value = current;
    }
  });

  const pageMaxText = document.createElement("span");
  pageMaxText.id = "page-max-display";
  pageMaxText.textContent = `/${max}`;
  pageDiv.append(pageText, pageInput, pageMaxText);
  
  const nextBtn = document.createElement("button");
  nextBtn.id = "page-next-btn";
  nextBtn.type = "button";
  nextBtn.className = "btn btn-outline-primary btn-sm mx-1";
  nextBtn.innerHTML = '<i class="bi bi-chevron-right"></i>';
  nextBtn.onclick = nextPage;

  container.append(prevBtn, pageDiv, nextBtn);
  const slot = document.getElementById("pagination-slot") || document.getElementById("table-container");
  slot.appendChild(container);
}

/**
 * Updates pagination input values without recreating controls.
 * @param {number} current - Current page index shown in UI.
 * @param {number} max - Maximum page count.
 * @returns {void}
 */
function updatePaginationControls(current, max) {
  const pageInput = document.getElementById("page-index-input");
  if (pageInput) {
    pageInput.max = String(max);
    pageInput.value = String(current);
  }
  const pageMaxText = document.getElementById("page-max-display");
  if (pageMaxText) {
    pageMaxText.textContent = `/${max}`;
  }
}

/**
 * Navigates to previous page when available.
 * @returns {void}
 */
function previousPage() {
  if (currentPageIndex <= 0) return;
  loadPage(currentProjectID, currentPageIndex - 1, false, "edited",true)
    .catch((err) => {
      console.error("Navigation load failed:", err);
    });
}

/**
 * Navigates to next page when available.
 * @returns {void}
 */
function nextPage() {
  if (currentPageIndex >= nbrPageMax) return;
  loadPage(currentProjectID, currentPageIndex + 1, false, "edited",true)
    .catch((err) => {
      console.error("Navigation load failed:", err);
    });
}


/**
 * Workflow callback for Prochaine: move next, load OCR fallback, then persist range data.
 * @returns {Promise<void>}
 */
async function nextPageWithLoadAndPropagate() {
  if (currentPageIndex >= nbrPageMax) return;
  try {
    const isTableValid = validateTableForContinue();
    if (!isTableValid) return;

    const preservedTableData = collectTableDataForSave();
    if (!preservedTableData) return;

    endPageIndex = currentPageIndex + 1;
    updateRangeIndexDisplay();

    // Auto-save the current page's input and backfill any derived fields
    await autoSaveInputAndBackfill(preservedTableData);

    // Load the next page before propagating changes
    const loaded = await loadPage(currentProjectID, currentPageIndex + 1, false, "edited", false, false);
    if (!loaded) return;

    // Keep the same table values, then enrich empties from next-page OCR.
    extract_values = { ...preservedTableData };
    updateExistingTableValues(extract_values);
    await loadAndFillCurrentPageEmpty();

    
    //Save if current page is the last page
    if (currentPageIndex === nbrPageMax) {
      await autoSaveInputAndBackfill(collectTableDataForSave());
    }



  } catch (err) {
    console.error("Prochaine failed:", err);
  }
}

/**
 * Escapes HTML-sensitive characters for safe inline rendering in alerts.
 * @param {string} value - Raw text to escape.
 * @returns {string}
 */
function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Validates and normalizes a value according to parse rules.
 * @param {string} rawValue - Raw edited cell value.
 * @param {string|Array<string>|null|undefined} parseRule - Parse constraint from configuration.
 * @returns {{valid: boolean, normalized: string}}
 */
function validateAndNormalizeByParse(rawValue, parseRule) {
  const original = String(rawValue || "").trim();
  if (isEmptyValue(original)) return { valid: true, normalized: "" };

  const parseNumber = (value) => {
    const normalized = String(value).replace(",", ".").trim();
    if (!/^[-+]?\d+(\.\d+)?$/.test(normalized)) return null;
    const asNumber = Number(normalized);
    return Number.isFinite(asNumber) ? asNumber : null;
  };

  if (Array.isArray(parseRule)) {
    const allowed = parseRule.map(v => String(v).trim()).filter(v => v !== "");
    if (allowed.includes(original)) {
      return { valid: true, normalized: original };
    }
    const inputNumber = parseNumber(original);
    if (inputNumber !== null) {
      for (const allowedValue of allowed) {
        const allowedNumber = parseNumber(allowedValue);
        if (allowedNumber !== null && allowedNumber === inputNumber) {
          return { valid: true, normalized: allowedValue };
        }
      }
    }
    return { valid: false, normalized: original };
  }

  if (typeof parseRule !== "string") {
    return { valid: true, normalized: original };
  }

  const normalizedRule = parseRule.trim().toLowerCase();
  if (!normalizedRule) {
    return { valid: true, normalized: original };
  }

  if (normalizedRule === "integer") {
    return { valid: /^[-+]?\d+$/.test(original), normalized: original };
  }

  if (normalizedRule === "float") {
    const floatNumber = parseNumber(original);
    if (floatNumber === null) return { valid: false, normalized: original };
    const normalizedFloat = floatNumber.toFixed(1).replace(".", ",");
    return { valid: true, normalized: normalizedFloat };
  }

  if (normalizedRule === "date") {
    const match = original.match(/^(\d{2})-(\d{2})-(\d{2})$/);
    if (!match) return { valid: false, normalized: original };
    const day = Number(match[1]);
    const month = Number(match[2]);
    const year = Number(match[3]);
    const fullYear = 2000 + year;
    const dateObj = new Date(fullYear, month - 1, day);
    const isValidDate = dateObj.getFullYear() === fullYear
      && (dateObj.getMonth() + 1) === month
      && dateObj.getDate() === day;
    return { valid: isValidDate, normalized: original };
  }

  if (normalizedRule === "4 digit" || normalizedRule.includes("4 digit")) {
    return { valid: /^\d{4}$/.test(original), normalized: original };
  }

  if (normalizedRule.startsWith("one of ")) {
    const allowed = parseRule
      .slice(7)
      .split(",")
      .map(v => v.trim())
      .filter(v => v !== "");
    const listValidation = validateAndNormalizeByParse(original, allowed);
    return listValidation;
  }

  return { valid: true, normalized: original };
}

/**
 * Validates all non-empty table values before the "Copier" workflow.
 * Invalid cells are highlighted and the workflow is blocked until corrected.
 * @returns {boolean}
 */
function validateTableForContinue() {
  const table = document.querySelector(".param-table");
  if (!table) return true;

  const errors = [];
  table.querySelectorAll("tbody tr").forEach(row => {
    if (row.classList.contains("group-separator-row")) return;

    const keyCell = row.querySelector("td.param-cell");
    const valueCell = row.querySelector("td.value-cell");
    if (!keyCell || !valueCell) return;

    valueCell.style.border = "";

    const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
    if (!key) return;

    const currentValue = (valueCell.textContent || "").trim();
    if (isEmptyValue(currentValue)) return;

    const parseRule = field_parse[key];
    const validation = validateAndNormalizeByParse(currentValue, parseRule);
    if (!validation.valid) {
      valueCell.style.border = "2px solid #dc3545";
      const visibleLabel = (field_text[key] || keyCell.textContent || key).trim();
      const expected = Array.isArray(parseRule)
        ? parseRule.join(", ")
        : (parseRule || "format valide");
      errors.push(`• ${escapeHtml(visibleLabel)} : attendu « ${escapeHtml(expected)} »`);
      return;
    }

    if (validation.normalized !== currentValue) {
      valueCell.textContent = validation.normalized;
    }
    extract_values[key] = validation.normalized;
  });

  if (errors.length > 0) {
    return false;
  }

  return true;
}

/**
 * Checks whether a value should be treated as empty in editable cells.
 * @param {*} v - Candidate value.
 * @returns {boolean}
 */
function isEmptyValue(v) {
  return v === null || v === undefined || (typeof v === "string" && v.trim() === "");
}

/**
 * Parses nullable index fields coming from JSON payloads.
 * @param {*} value - Raw index value from server or local state.
 * @returns {number|null} Integer index or null when invalid/empty.
 */
function parseNullableIndex(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" && value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : null;
}

/**
 * Attaches only start/end index metadata to a payload.
 * @param {Object} data - Data payload to enrich.
 * @returns {Object} Copy containing start/end index fields.
 */
function withStartEndMetadata(data) {
  const nextData = { ...(data || {}) };
  const startIndex = parseNullableIndex(startPageIndex);
  const endIndex = parseNullableIndex(endPageIndex);
  nextData.start_index = startIndex;
  nextData.end_index = endIndex;
  return nextData;
}

/**
 * Attaches index metadata to a payload before persistence.
 * @param {Object} data - Data payload to enrich.
 * @returns {Object} Copy containing start/end/doc index fields.
 */
function withPageRangeMetadata(data) {
  const nextData = withStartEndMetadata(data);
  const nextDocIndex = parseNullableIndex(docIndex);
  nextData.doc_index = nextDocIndex;
  return nextData;
}

/**
 * Removes non-editable metadata keys from payloads used by the table renderer.
 * @param {Object} data - Source payload.
 * @returns {Object}
 */
function stripPageRangeMetadata(data) {
  if (!data || typeof data !== "object") return data;
  const nextData = { ...data };
  delete nextData.start_index;
  delete nextData.end_index;
  delete nextData.doc_index;
  return nextData;
}

// === TABLE UI ===
/**
 * Generates the editable parameter table from current page data.
 * @param {Object} data - Key/value table data.
 * @param {string} [containerId="table-values-container"] - Target container element ID.
 * @returns {void}
 */
function generateEditableTable(data, containerId = "table-values-container") {
  const container = document.getElementById(containerId) || document.getElementById("table-container");
  if (!container) return;

  const table = document.createElement("table");
  table.className = "param-table";

  const thead = table.createTHead();
  const headerRow = thead.insertRow();
  ["Paramètre", "Valeurs éditées"].forEach(text => {
    const th = document.createElement("th");
    th.textContent = text;
    headerRow.appendChild(th);
  });

  const tbody = document.createElement("tbody");
  const subsectionLabelById = {};
  if (Array.isArray(subsections)) {
    subsections.forEach(section => {
      if (section && section.id) {
        subsectionLabelById[section.id] = section.label || section.id;
      }
    });
  }
  let lastSubsectionId = null;

  for (const [key, value] of Object.entries(data)) {
    if (["start_index", "end_index", "doc_index"].includes(key)) continue;
    if (field_visibility[key] === false) continue;
    const currentSubsectionId = field_subsection[key] || null;
    if (currentSubsectionId && currentSubsectionId !== lastSubsectionId) {
      const separatorRow = document.createElement("tr");
      separatorRow.className = "group-separator-row";
      const separatorCell = document.createElement("td");
      separatorCell.colSpan = 2;
      separatorCell.textContent = subsectionLabelById[currentSubsectionId] || currentSubsectionId;
      separatorRow.appendChild(separatorCell);
      tbody.appendChild(separatorRow);
      lastSubsectionId = currentSubsectionId;
    }

    const row = document.createElement("tr");

    const hasMappedColor = currentCategory.startsWith('bilan_lipidique_')
      && labelColors[key];
    const isQuestion = field_type[key] === "question";
    const defaultLabelBgColor = isQuestion ? "rgba(255, 193, 7, 0.18)" : "rgba(80, 160, 255, 0.12)";
    const defaultValueBgColor = isQuestion ? "rgba(255, 193, 7, 0.10)" : "rgba(80, 160, 255, 0.12)";
    const labelBgColor = hasMappedColor && labelColors[key].label
      ? labelColors[key].label
      : defaultLabelBgColor;
    const valueBgColor = hasMappedColor && labelColors[key].value
      ? labelColors[key].value
      : defaultValueBgColor;

    const paramCell = document.createElement("td");
    paramCell.className = "param-cell";
    paramCell.contentEditable = "false";
    paramCell.textContent = field_text[key] || key;
    paramCell.dataset.originalKey = key;
    paramCell.style.backgroundColor = labelBgColor;

    const valueCell = document.createElement("td");
    valueCell.className = "value-cell";
    valueCell.contentEditable = "true";
    valueCell.textContent = value !== null ? value : "";
    valueCell.style.backgroundColor = valueBgColor;

    paramCell.addEventListener("input", () => {
      const oldKey = paramCell.dataset.originalKey;
      const newKey = paramCell.textContent.trim();

      if (newKey && newKey !== oldKey && !(newKey in data)) {
        data[newKey] = data[oldKey];
        delete data[oldKey];
        paramCell.dataset.originalKey = newKey;
      }
    });

    valueCell.addEventListener("input", () => {
      const currentKey = paramCell.dataset.originalKey;
      data[currentKey] = valueCell.textContent.trim();
      extract_values[currentKey] = valueCell.textContent.trim();
      scheduleAutoSaveFromInput();
    });

    row.append(paramCell, valueCell);
    tbody.appendChild(row);
  }

  table.appendChild(tbody);
  container.appendChild(table);
}

// === SYNC TO SERVER ===
/**
 * Reads edited values from DOM and prepares a save-ready payload.
 * @returns {Object|null} Payload including metadata, or null when table is absent.
 */
function collectTableDataForSave() {
  const table = document.querySelector(".param-table");
  if (!table) return null;

  const data = stripPageRangeMetadata({ ...extract_values });
  table.querySelectorAll("tbody tr").forEach(row => {
    if (row.classList.contains("group-separator-row")) return;
    const keyCell = row.querySelector("td.param-cell");
    const valueCell = row.querySelector("td.value-cell");
    if (!keyCell || !valueCell) return;
    const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
    const value = valueCell.textContent.trim();
    if (key) {
      data[key] = value;
      extract_values[key] = value;
    }
  });
  return withPageRangeMetadata(data);
}


/**
 * Saves payload to a specific page JSON file through backend API.
 * @param {number} pageIndex - 1-based logical page index.
 * @param {Object} data - Payload to persist.
 * @returns {Promise<Object|null>} Server response payload.
 */
async function saveTableDataToPageIndex(pageIndex, data) {
  if (!data || !currentProjectID) return null;
  const pageRef = currentFileList[pageIndex];
  if (!pageRef) return null;

  const formData = new FormData();
  const payload = withStartEndMetadata(data);
  formData.append("project_id", currentProjectID);
  formData.append("document_id", pageRef.document_id);
  formData.append("filename", `table_page_${pageRef.page}.json`);
  formData.append("data", JSON.stringify(payload));
  // console.log("Saving data for page index:", pageIndex, "with payload:", payload);
  
  const response = await fetch("/put_data", { method: "POST", body: formData });
  const responsePayload = await response.json();
  if (!response.ok) {
    throw new Error(responsePayload.error || `Unable to save page index ${pageIndex}`);
  }
  return responsePayload;
}

/**
 * Loads the saved table JSON for each page in a range, updates only start/end indices,
 * then writes the files back to the server without using local staging data.
 * @param {number} startIndex - First page index in the range.
 * @param {number} endIndex - Last page index in the range.
 * @returns {Promise<void>}
 */
async function updateRangeIndexesOnServer(startIndex, endIndex) {
  if (!Number.isInteger(startIndex) || !Number.isInteger(endIndex) || endIndex < startIndex) {
    return;
  }

  for (let i = startIndex; i <= endIndex; i++) {
    const pageRef = currentFileList[i];
    if (!pageRef) continue;

    const response = await fetch(`/get_data/${currentProjectID}/${pageRef.document_id}/table_page_${pageRef.page}.json?source=edited`);
    if (!response.ok) continue;
    const payload = await response.json();
    const rawData = payload && typeof payload.data_string === "string"
      ? JSON.parse(payload.data_string)
      : (payload || {});

    const nextData = { ...rawData };
    nextData.start_index = startIndex;
    nextData.end_index = endIndex;

    const formData = new FormData();
    formData.append("project_id", currentProjectID);
    formData.append("document_id", pageRef.document_id);
    formData.append("filename", `table_page_${pageRef.page}.json`);
    formData.append("data", JSON.stringify(nextData));

    const saveResponse = await fetch("/put_data", { method: "POST", body: formData });
    if (!saveResponse.ok) {
      const errorPayload = await saveResponse.json().catch(() => ({ error: "Unable to save range metadata" }));
      throw new Error(errorPayload.error || `Unable to save page index ${i}`);
    }
  }
}

/**
 * Nouveau workflow: clears editable values, reloads OCR source, resets range and increments doc index.
 * @returns {Promise<void>}
 */
async function startNewRangeFromRaw() {
  const table = document.querySelector(".param-table");
  if (!table) return;

  try {
    const currentDocIndex = Number.isInteger(docIndex) ? docIndex : Number(extract_values?.doc_index);
    const isSamePageAsLastNew = lastNewIncrementPageIndex === currentPageIndex;
    const nextDocIndex = currentPageIndex === 1
      ? 1
      : Number.isInteger(currentDocIndex)
        ? (isSamePageAsLastNew ? currentDocIndex : currentDocIndex + 1)
        : 1;

    // Update the previous range metadata directly on the server by reloading each saved file.
    const previousStartIndex = startPageIndex;
    const previousEndIndex = currentPageIndex - 1;
    if (Number.isInteger(previousStartIndex) && Number.isInteger(previousEndIndex)) {
      await updateRangeIndexesOnServer(previousStartIndex, previousEndIndex);
    }

    // 4) clear table
    table.querySelectorAll("tbody tr").forEach(row => {
      if (row.classList.contains("group-separator-row")) return;
      const keyCell = row.querySelector("td.param-cell");
      const valueCell = row.querySelector("td.value-cell");
      if (!keyCell || !valueCell) return;
      valueCell.textContent = "";
      const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
      if (key) {
        extract_values[key] = "";
      }
    });


    // 5) load raw data from current page
    await loadPage(currentProjectID, currentPageIndex, false, "raw", false);

    // 6) keep range/doc metadata for the new work segment
    startPageIndex = currentPageIndex;
    endPageIndex = currentPageIndex;
    docIndex = nextDocIndex;
    lastNewIncrementPageIndex = currentPageIndex;
    extract_values.start_index = startPageIndex;
    extract_values.end_index = endPageIndex;
    extract_values.doc_index = docIndex;
    updateRangeIndexDisplay();
    
  } catch (err) {
    console.error("Nouveau failed:", err);
  }
}

/**
 * Fills empty edited cells with OCR values from current page payload.
 * @returns {Promise<void>}
 */
async function loadAndFillCurrentPageEmpty() {
  try {
    const table = document.querySelector(".param-table");
    if (!table) return;

    table.querySelectorAll("tbody tr").forEach(row => {
      if (row.classList.contains("group-separator-row")) return;
      const keyCell = row.querySelector("td.param-cell");
      const valueCell = row.querySelector("td.value-cell");
      if (!keyCell || !valueCell) return;

      const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
      if (!key) return;

      const rawValue = raw_extract_values[key] !== null && raw_extract_values[key] !== undefined
        ? String(raw_extract_values[key]).trim()
        : "";
      const currentCellValue = (valueCell.textContent || "").trim();

      if (isEmptyValue(currentCellValue) && !isEmptyValue(rawValue)) {
        valueCell.textContent = String(rawValue);
        extract_values[key] = String(rawValue);
      }
    });
  } catch (err) {
    console.error("Load failed:", err);
  }
}


// === ROTATE & ZOOM CALLBACKS ===
let currentRotation = 0;
let currentScale = 1;
const minScale = 0.2;
const maxScale = 3;

/**
 * Registers rotate/zoom/reset toolbar handlers for the page image viewer.
 * @returns {void}
 */
function initButtonCallback(){
  const btnRotate = document.getElementById('btn-rotate');
  const btnZoomIn = document.getElementById('btn-zoom-in');
  const btnZoomOut = document.getElementById('btn-zoom-out');
  const btnReset = document.getElementById('btn-reset');

  if (btnRotate) {
    btnRotate.addEventListener('click', () => {
      currentRotation = (currentRotation + 90) % 360;
      displayPage(currentProjectID, currentDocID, currentDocPage,true,true);
    });
  }
  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
      currentScale = Math.min(currentScale + 0.2, maxScale);
      displayPage(currentProjectID, currentDocID, currentDocPage,true,true);
    });
  }
  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
      currentScale = Math.max(currentScale - 0.2, minScale);
      displayPage(currentProjectID, currentDocID, currentDocPage,true,true);
    });
  }
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      currentRotation = 0;
      currentScale = 1;
      displayPage(currentProjectID, currentDocID, currentDocPage,true,true);
    });
  }
}

// === ON LOAD ===
window.addEventListener('DOMContentLoaded', async function () {

   //Read project in url
  const urlParams = new URLSearchParams(window.location.search);
  const projectId = urlParams.get('project');
  const documentId = urlParams.get('document');
  // Initialize button callbacks
  initButtonCallback();

  startSpinner("Chargement du projet...");
  //Load project
  project_data = await ProjectManager.getProject(projectId);

  if (project_data.length > 0) {
    startPageIndex = null;
    endPageIndex = null;
    docIndex = null;
    hasRenderedTableSection = false;
    createFileList(projectId, documentId, project_data);

    //Display First page
    await loadPage(projectId, currentPageIndex,true,'edited',true);


    //display project data in fileList
    displayInfo(`📁 Fichier: ${project_data[0].filename}`);


  }
  else {
    displayInfo("📁 Fichier: Aucun fichier trouvé");
  }
  stopSpinner();

});

// Parcourt tous les bbox d'un objet (ex: label_bbox) et ajuste la hauteur si elle dépasse une valeur seuil
/**
 * Converts polygon corner coordinates into width/height-like values for debug usage.
 * @param {Object} bboxObj - Bbox map keyed by label.
 * @param {number} maxHeight - Kept for compatibility; currently unused.
 * @returns {Object|undefined} Mutated bbox object, or undefined when input is absent.
 */
function adjustBboxHeight(bboxObj, maxHeight) {
    // bboxObj : { label1: [x, y, w, h], ... }
    // maxHeight : valeur maximale autorisée pour la hauteur (h)
    if (!bboxObj) return;
    Object.keys(bboxObj).forEach(function(label) {
        let bbox = bboxObj[label];
        if (Array.isArray(bbox) && bbox.length === 4) {
            // bbox = [x, y, w, h]
            bbox[3] = Math.max(30, bbox[3] - bbox[1]); // Assure que la hauteur est au moins 30
            bbox[2] = bbox[2] - bbox[0]; // Assure que la largeur est au moins 1
        }
    });
    return bboxObj
}
