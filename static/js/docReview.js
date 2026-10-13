// === GLOBAL STATE ===
let page_id = '';
let extract_values = {};
let raw_extract_values = {};
let previousPageHeaderValues = {};
let previousPageTableData = {};
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
 * @param {boolean} [renderTable=true] - Whether to rebuild/refresh the table section after image render.
 * @returns {Promise<boolean|undefined>} True when page data is loaded; false/undefined otherwise.
 */
async function loadPage(project_id, index, init_scroll=false, sourceMode="edited", renderTable=true) {
  
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
    const previousPageIndex = index > 1 ? index - 1 : null;
    const previousTableUrl = previousPageIndex
      ? `/get_data/${project_id}/${currentDocID}/table_page_${previousPageIndex}.json?source=${encodeURIComponent(sourceMode)}`
      : null;
    const responses = await Promise.all([
        fetch(`/get_data/${project_id}/${currentDocID}/label_bbox_${page_id}.json?source=${encodeURIComponent(sourceMode)}`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/value_bbox_${page_id}.json?source=${encodeURIComponent(sourceMode)}`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/table_${page_id}.json?source=${encodeURIComponent(sourceMode)}`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/table_${page_id}.json?source=raw`).then(res => res.json()).catch(() => ({})),
        fetch(`/get_raw_data/${project_id}/${currentDocID}/all_blocks_${page_id}.json`).then(res => res.json()).catch(() => []),
        fetch(`/get_raw_data/${project_id}/${currentDocID}/grid_${page_id}.json`).then(res => res.json()).catch(() => ({})),
        previousTableUrl ? fetch(previousTableUrl).then(res => res.json()).catch(() => ({})) : Promise.resolve({})
    ]);
    if (!responses[0].data_string || !responses[1].data_string || !responses[2].data_string) {
        // Handle empty responses
      return false;
    }
    label_bbox = JSON.parse(responses[0].data_string || '{}');
    value_bbox = JSON.parse(responses[1].data_string || '{}');
    extract_values = JSON.parse(responses[2].data_string || '{}');
    raw_extract_values = JSON.parse(responses[3]?.data_string || '{}');
    previousPageHeaderValues = {};
    previousPageTableData = {};
    if (responses[6]?.data_string) {
      const previousData = JSON.parse(responses[6].data_string || '{}');
      if (previousData && typeof previousData === "object") {
        previousPageHeaderValues = previousData;
        previousPageTableData = previousData;
      }
    }
    // console.log("Raw extract values:", raw_extract_values);
    field_visibility = responses[2].field_visibility || {};
    field_text = responses[2].field_text || {};
    field_type = responses[2].field_type || {};
    field_parse = responses[2].field_parse || {};
    field_subsection = responses[2].field_subsection || {};
    subsections = responses[2].subsections || [];
    all_blocks = responses[4] || [];
    const gridData = responses[5] || {};
    grid_cells = gridData.cells || [];

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
    const contentEntries = orderedEntries;

    const hiddenEntries = [];
    const groupBuckets = new Map();
    contentEntries.forEach(([key, value], indexInOrder) => {
      if (field_visibility[key] === false || shouldHideFormulaireSuiviHeaderRow(key)) {
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
    extract_values = Object.fromEntries([...reorderedContentEntries, ...hiddenEntries]);

    // Header actions (Nouveau / Prochaine)
    createTopActionControls();

    // Génération du tableau d'en-tête puis du tableau éditable général
    generateHeaderTable(extract_values);
    // Génération du tableau éditable général
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
    if (!key) return;
    const nextValue = data[key] !== undefined && data[key] !== null ? data[key] : raw_extract_values?.[key];
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
 * Persists the current page's edited values individually.
 * @param {Object|null} [dataOverride=null] - Optional payload overriding table collection.
 * @returns {Promise<void>}
 */
async function autoSaveInputAndBackfill(dataOverride = null) {
  const data = dataOverride || collectTableDataForSave();
  if (!data) return;

  if (!Number.isInteger(currentPageIndex)) {
    return;
  }

  await saveTableDataToPageIndex(currentPageIndex, data);
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
      const data = collectTableDataForSave();
      if (data) {
        await saveTableDataToPageIndex(currentPageIndex, data);
      }
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

  const activeCategory = (typeof key_order !== "undefined" ? key_order : (typeof currentCategory !== "undefined" ? currentCategory : ""));
  if (["bilan_lipidique_1", "bilan_lipidique_2"].includes(activeCategory)) {
    return;
  }

  const row = document.createElement("div");
  row.className = "table-header-actions";
  const instructions = document.createElement("div");
  instructions.className = "table-header-actions-instructions";
   const instructionLine2 = document.createElement("div");
  instructionLine2.innerHTML = "<strong>Note :</strong> cliquez sur « Copier » pour copier les valeurs de l'entête de la page précédente.";
  instructions.append(instructionLine2);
  const buttons = document.createElement("div");
  buttons.className = "table-header-actions-buttons";

  const prochaineBtn = document.createElement("button");
  prochaineBtn.id = "next-workflow-btn";
  prochaineBtn.type = "button";
  prochaineBtn.className = "btn btn-outline-primary btn-sm save-table-btn";
  prochaineBtn.textContent = "Copier";
  prochaineBtn.onclick = copyPreviousPageValuesToEditedAndSave;

  buttons.append(prochaineBtn);

  const controlsRow = document.createElement("div");
  controlsRow.className = "table-header-controls-row";
  controlsRow.append(buttons);

  row.append(instructions, controlsRow);
  slot.appendChild(row);
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
 * Copies values shown in the "Page précédente" column into the editable value cells,
 * then persists the current page to the server.
 * @returns {Promise<void>}
 */
async function copyPreviousPageValuesToEditedAndSave() {
  if (!previousPageTableData || typeof previousPageTableData !== "object") return;

  const headerRows = document.querySelectorAll(".header-summary-table tbody tr");
  headerRows.forEach(row => {
    const keyCell = row.querySelector("td.param-cell");
    const editCell = row.querySelector("td.editable-header-cell");
    if (!keyCell || !editCell) return;

    const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
    if (!key) return;

    const value = previousPageTableData[key] ?? previousPageHeaderValues[key] ?? "";
    const stringValue = value === null || value === undefined ? "" : String(value);
    editCell.textContent = stringValue;

    if (key === "Phase") {
      const cleanedPhase = String(stringValue).replace(/^P/i, "").trim();
      extract_values.Phase = cleanedPhase;
      const currentVisit = parsePhaseAndVisit(extract_values.Visites || "").visit;
      const combined = `${cleanedPhase ? `P${cleanedPhase}` : ""}${currentVisit ? `V${currentVisit}` : ""}`.trim();
      extract_values.Visites = combined;
      return;
    }

    if (key === "Visite") {
      const cleanedVisit = String(stringValue).replace(/^V/i, "").trim();
      extract_values.Visite = cleanedVisit;
      const currentPhase = parsePhaseAndVisit(extract_values.Visites || "").phase;
      const combined = `${currentPhase ? `P${currentPhase}` : ""}${cleanedVisit ? `V${cleanedVisit}` : ""}`.trim();
      extract_values.Visites = combined;
      return;
    }

    extract_values[key] = stringValue;
  });

  const table = document.querySelector(".param-table");
  if (table) {
    table.querySelectorAll("tbody tr").forEach(row => {
      if (row.classList.contains("group-separator-row")) return;
      const keyCell = row.querySelector("td.param-cell");
      const valueCell = row.querySelector("td.value-cell");
      if (!keyCell || !valueCell) return;

      const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
      if (!key) return;

      const value = previousPageTableData[key] ?? "";
      const stringValue = value === null || value === undefined ? "" : String(value);
      valueCell.textContent = stringValue;
      extract_values[key] = stringValue;
    });
  }

  const payload = collectTableDataForSave();
  if (!payload) return;
  await saveTableDataToPageIndex(currentPageIndex, payload);
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

// === TABLE UI ===
/**
 * Extracts a phase/visit pair from a combined "Visites" value such as P1V2 or P1.
 * @param {string|number|null|undefined} value - Source value.
 * @returns {{phase:string, visit:string}}
 */
function parsePhaseAndVisit(value) {
  const raw = value === null || value === undefined ? "" : String(value).trim();
  if (!raw) return { phase: "", visit: "" };
  const normalized = raw.toUpperCase();
  const phaseMatch = normalized.match(/P?(\d+)/);
  const visitMatch = normalized.match(/V(\d+)/);
  return {
    phase: phaseMatch ? phaseMatch[1] : "",
    visit: visitMatch ? visitMatch[1] : "",
  };
}

/**
 * Renders the dedicated header summary table for Formulaire de suivi.
 * @param {Object} data - Current page value map.
 * @returns {void}
 */
function shouldHideFormulaireSuiviHeaderRow(key) {
  if (currentCategory !== "formulaire_suivi") return false;
  const normalizedKey = String(key || "").trim();
  const normalizedLabel = String(field_text[key] || "").trim();
  const hiddenKeys = new Set(["Visites", "date_visite", "Date d'observation (DD-MM-YY)", "nomat", "No du participant", "no_participant", "Phase", "Visite"]);
  const hiddenLabels = new Set([
    "Phase",
    "Visite",
    "Date de visite (DD-MM-YY)",
    "Date d'observation (DD-MM-YY)",
    "# du participant (4 chiffres)",
    "No du participant"
  ]);
  return hiddenKeys.has(normalizedKey) || hiddenLabels.has(normalizedKey) || hiddenLabels.has(normalizedLabel);
}

function resolveParticipantHeaderValue(payload) {
  if (!payload || typeof payload !== "object") return "";
  return payload["No du participant"] ?? payload.nomat ?? payload["# du participant (4 chiffres)"] ?? payload["No du participant (4 chiffres)"] ?? "";
}

function resolveObservationDateHeaderValue(payload) {
  if (!payload || typeof payload !== "object") return "";
  return payload["Date d'observation (DD-MM-YY)"] ?? payload.date_visite ?? payload["Date de visite (DD-MM-YY)"] ?? "";
}

function generateHeaderTable(data) {
  const tableValuesContainer = document.getElementById("table-values-container");
  if (!tableValuesContainer || currentCategory !== "formulaire_suivi") return;

  const table = document.createElement("table");
  table.className = "param-table header-summary-table";

  const headerTitleRow = document.createElement("tr");
  const headerTitleCell = document.createElement("td");
  headerTitleCell.colSpan = 3;
  headerTitleCell.textContent = "Entête";
  headerTitleCell.style.textAlign = "left";
  headerTitleCell.style.fontWeight = "700";
  headerTitleCell.style.backgroundColor = "#e8f7e8";
  headerTitleCell.style.color = "#1f6b2f";
  headerTitleCell.style.textTransform = "uppercase";
  headerTitleCell.style.letterSpacing = "0.03em";
  headerTitleCell.style.borderTop = "2px solid #9dd49d";
  headerTitleRow.appendChild(headerTitleCell);
  table.appendChild(headerTitleRow);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Paramètre", "Page précédente", "Valeurs éditées"].forEach(text => {
    const th = document.createElement("th");
    th.textContent = text;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const rows = [
    { label: "Phase", getter: () => data?.Phase ?? parsePhaseAndVisit(data?.Visites || "").phase, previousGetter: () => previousPageHeaderValues?.Phase ?? parsePhaseAndVisit(previousPageHeaderValues?.Visites || "").phase, key: "Phase" },
    { label: "Visite", getter: () => data?.Visite ?? parsePhaseAndVisit(data?.Visites || "").visit, previousGetter: () => previousPageHeaderValues?.Visite ?? parsePhaseAndVisit(previousPageHeaderValues?.Visites || "").visit, key: "Visite" },
    { label: "Date d'observation (DD-MM-YY)", getter: () => resolveObservationDateHeaderValue(data), previousGetter: () => resolveObservationDateHeaderValue(previousPageHeaderValues), key: "Date d'observation (DD-MM-YY)" },
    { label: "No du participant", getter: () => resolveParticipantHeaderValue(data), previousGetter: () => resolveParticipantHeaderValue(previousPageHeaderValues), key: "No du participant" },
  ];

  rows.forEach(rowDef => {
    const row = document.createElement("tr");
    const labelCell = document.createElement("td");
    labelCell.textContent = rowDef.label;
    labelCell.className = "param-cell";
    labelCell.dataset.originalKey = rowDef.key;

    const prevCell = document.createElement("td");
    const previousValue = rowDef.previousGetter ? rowDef.previousGetter() : "";
    prevCell.textContent = previousValue !== undefined && previousValue !== null ? String(previousValue) : "";
    prevCell.className = "value-cell previous-value-cell";
    prevCell.dataset.role = "previous";

    const editCell = document.createElement("td");
    const editValue = rowDef.getter();
    editCell.textContent = editValue !== undefined && editValue !== null ? String(editValue) : "";
    editCell.className = "value-cell editable-header-cell";
    editCell.contentEditable = "true";
    editCell.dataset.originalKey = rowDef.key;
    editCell.dataset.role = "edited";

    editCell.addEventListener("input", () => {
      const nextValue = editCell.textContent.trim();

      if (rowDef.key === "Phase") {
        const cleanedPhase = String(nextValue).replace(/^P/i, "").trim();
        data.Phase = cleanedPhase;
        extract_values.Phase = cleanedPhase;

        const currentVisit = parsePhaseAndVisit(data.Visites || "").visit;
        const combined = `${cleanedPhase ? `P${cleanedPhase}` : ""}${currentVisit ? `V${currentVisit}` : ""}`.trim();
        data.Visites = combined;
        extract_values.Visites = combined;
      } else if (rowDef.key === "Visite") {
        const cleanedVisit = String(nextValue).replace(/^V/i, "").trim();
        data.Visite = cleanedVisit;
        extract_values.Visite = cleanedVisit;

        const currentPhase = parsePhaseAndVisit(data.Visites || "").phase;
        const combined = `${currentPhase ? `P${currentPhase}` : ""}${cleanedVisit ? `V${cleanedVisit}` : ""}`.trim();
        data.Visites = combined;
        extract_values.Visites = combined;
      } else if (rowDef.key === "No du participant") {
        data["No du participant"] = nextValue;
        data.nomat = nextValue;
        extract_values["No du participant"] = nextValue;
        extract_values.nomat = nextValue;
      } else if (rowDef.key === "Date d'observation (DD-MM-YY)") {
        data["Date d'observation (DD-MM-YY)"] = nextValue;
        data.date_visite = nextValue;
        extract_values["Date d'observation (DD-MM-YY)"] = nextValue;
        extract_values.date_visite = nextValue;
      } else {
        data[rowDef.key] = nextValue;
        extract_values[rowDef.key] = nextValue;
      }
      scheduleAutoSaveFromInput();
    });

    row.append(labelCell, prevCell, editCell);
    tbody.appendChild(row);
  });

  table.appendChild(tbody);
  tableValuesContainer.appendChild(table);
}

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

  const hiddenSecondaryKeys = new Set([
    "group_rando",
    "mode_renc",
    "weight_lbs",
    "weight_kg",
    "poids_m",
    "waistc",
    "jb_remis",
    "fq_comp",
    "date_rappel",
    "prop_gac",
    "grains_entiers",
    "prot_veg",
    "priv_eau",
    "prot_r24",
    "lip_r24",
    "gluc_r24",
    "act_phys",
    "sommeil",
    "prot_repas",
    "gras_insat",
    "fruit_leg",
    "prod_lait",
    "faib_ig",
    "capsa",
    "alim_rassa",
    "fibr_r24",
    "calci_r24",
    "port_fecul",
    "port_viand",
    "fruit_sucr",
    "port_leg",
    "port_laits",
    "port_mg",
    "def_cal"
  ]);

  for (const [key, value] of Object.entries(data)) {
    if (field_visibility[key] === false) continue;
    if (shouldHideFormulaireSuiviHeaderRow(key)) continue;
    if (hiddenSecondaryKeys.has(key)) continue;
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
    const displayValue = value !== undefined && value !== null ? value : (raw_extract_values?.[key] ?? "");
    valueCell.textContent = displayValue !== null && displayValue !== undefined ? String(displayValue) : "";
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
function sanitizePayloadForSave(payload) {
  if (!payload || typeof payload !== "object") return payload;
  const forbiddenKeys = new Set([
    "Visites",
    "nomat",
    "date_visite",
    "group_rando",
    "mode_renc",
    "weight_lbs",
    "weight_kg",
    "poids_m",
    "waistc",
    "jb_remis",
    "fq_comp",
    "date_rappel",
    "prop_gac",
    "grains_entiers",
    "prot_veg",
    "priv_eau",
    "prot_r24",
    "lip_r24",
    "gluc_r24",
    "act_phys",
    "sommeil",
    "prot_repas",
    "gras_insat",
    "fruit_leg",
    "prod_lait",
    "faib_ig",
    "capsa",
    "alim_rassa",
    "fibr_r24",
    "calci_r24",
    "port_fecul",
    "port_viand",
    "fruit_sucr",
    "port_leg",
    "port_laits",
    "port_mg",
    "def_cal"
  ]);

  const sanitized = {};
  Object.entries(payload).forEach(([key, value]) => {
    if (forbiddenKeys.has(key)) return;
    sanitized[key] = value;
  });
  return sanitized;
}

function collectTableDataForSave() {
  const rows = document.querySelectorAll(".header-summary-table tbody tr, .param-table tbody tr");
  if (!rows.length) return null;

  const data = { ...extract_values };
  rows.forEach(row => {
    if (row.classList.contains("group-separator-row")) return;

    const keyCell = row.querySelector("td.param-cell");
    if (!keyCell) return;

    const key = keyCell.dataset.originalKey || keyCell.textContent.trim();
    if (!key) return;

    const editedCell = row.querySelector("td.editable-header-cell")
      || row.querySelector("td.value-cell:not(.previous-value-cell)")
      || row.querySelector("td.value-cell")
      || (row.cells && row.cells.length >= 3 ? row.cells[2] : null);
    if (!editedCell) return;

    const value = (editedCell.textContent || "").trim();
    if (key === "Nom du participant" || key === "No du participant") {
      data["No du participant"] = value;
      extract_values["No du participant"] = value;
    } else if (key === "Date d'observation (DD-MM-YY)" || key === "date_visite") {
      data["Date d'observation (DD-MM-YY)"] = value;
      extract_values["Date d'observation (DD-MM-YY)"] = value;
    } else {
      data[key] = value;
      extract_values[key] = value;
    }
  });

  return data;
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
  const payload = sanitizePayloadForSave(data);
  formData.append("project_id", currentProjectID);
  formData.append("document_id", pageRef.document_id);
  formData.append("filename", `table_page_${pageRef.page}.json`);
  formData.append("data", JSON.stringify(payload));
  console.log("Saving data for page index:", pageIndex, "with payload:", payload);
  
  const response = await fetch("/put_data", { method: "POST", body: formData });
  const responsePayload = await response.json();
  if (!response.ok) {
    throw new Error(responsePayload.error || `Unable to save page index ${pageIndex}`);
  }
  return responsePayload;
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
  hasRenderedTableSection = false;
    createFileList(projectId, documentId, project_data);

    //Display First page
    await loadPage(projectId, currentPageIndex,true,'edited');


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
