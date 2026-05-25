// === GLOBAL STATE ===
let page_id = '';
let extract_values = {};
let label_bbox = {};
let value_bbox = {};
let all_blocks = [];
let checked_boxes = [];
let grid_cells = [];

let currentDocPage = 0;
let currentDocID = 0;
let currentProjectID = "";
let currentPageIndex = 0;
let currentFileList = [];

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
  "Cholestérol total": { label: `hsla(30, 90%, 40%,${bboxOpacity})`, value: `hsla(30, 90%, 60%,${bboxOpacity})` },
  "Triglycérides": { label: `hsla(180, 85%, 35%,${bboxOpacity})`, value: `hsla(180, 85%, 55%,${bboxOpacity})` },
  "Cholestérol-HDL": { label: `hsla(270, 85%, 45%,${bboxOpacity})`, value: `hsla(270, 85%, 65%,${bboxOpacity})` },
  "Cholestérol-LDL": { label: `hsla(60, 90%, 35%,${bboxOpacity})`, value: `hsla(60, 90%, 55%,${bboxOpacity})` },
  "Cholestérol non-HDL": { label: `hsla(330, 85%, 40%,${bboxOpacity})`, value: `hsla(330, 85%, 60%,${bboxOpacity})` },
  "Cholestérol-total/C-HDL": { label: `hsla(150, 85%, 35%,${bboxOpacity})`, value: `hsla(150, 85%, 55%,${bboxOpacity})` },
  "Glucose": { label: `hsla(210, 85%, 45%,${bboxOpacity})`, value: `hsla(210, 85%, 65%,${bboxOpacity})` },
  "Insuline": { label: `hsla(45, 90%, 40%,${bboxOpacity})`, value: `hsla(45, 90%, 60%,${bboxOpacity})` }
};

const tooltip = document.createElement("div");
tooltip.className = "tooltip";
document.body.appendChild(tooltip);

// === DISPLAY INFO ===
function displayInfo(info) {
  //display info in ocr-demo-title
  const title = document.getElementById("ocr-demo-title");
  title.innerHTML = `${info}`;

}
// Démarrer un spinner avec sweetalert
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
function stopSpinner() {
    Swal.close();
}

// Fonction pour créer la liste des fichiers
function createFileList(project_id, document_id, fileArray) {
  //loop in fileArray and add each file with its page number
  fileArray.forEach((file, index) => {
    // create a list on nbr_pages of document id in fileIndexList
    if (file.document_id==document_id) {
      for (let i = 0; i < file.nbr_pages; i++) {
          currentFileList.push({ document_id: file.document_id, page: i });
        }
        nbrPageMax += file.nbr_pages;
    }
  });
  currentProjectID = project_id;
}


// === MAIN LOADING FUNCTION ===
async function loadPage(project_id, index, init_scroll=false) {
  if (currentFileList.length === 0 || index < 0 || index >= nbrPageMax) {
    console.error("No files available for loading.");
    return;
  }
  try {

    currentPageIndex = index;
    currentDocPage = currentFileList[index].page;
    currentDocID = currentFileList[index].document_id;
    //start spinner cursor
    page_id = `page_${index+1}`;
    const responses = await Promise.all([
        fetch(`/get_data/${project_id}/${currentDocID}/label_bbox_${page_id}.json`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/value_bbox_${page_id}.json`).then(res => res.json()),
        fetch(`/get_data/${project_id}/${currentDocID}/table_${page_id}.json`).then(res => res.json()),
        fetch(`/get_raw_data/${project_id}/${currentDocID}/all_blocks_${page_id}.json`).then(res => res.json()).catch(() => []),
        fetch(`/get_raw_data/${project_id}/${currentDocID}/checked_boxes_${page_id}.json`).then(res => res.json()).catch(() => []),
        fetch(`/get_raw_data/${project_id}/${currentDocID}/grid_${page_id}.json`).then(res => res.json()).catch(() => ({}))
    ]);
    if (!responses[0].data_string || !responses[1].data_string || !responses[2].data_string) {
        // Handle empty responses
      return false;
    }
    label_bbox = JSON.parse(responses[0].data_string || '{}');
    value_bbox = JSON.parse(responses[1].data_string || '{}');
    extract_values = JSON.parse(responses[2].data_string || '{}');
    all_blocks = responses[3] || [];
    checked_boxes = responses[4] || [];
    const gridData = responses[5] || {};
    grid_cells = gridData.cells || [];
  // Exemple d'utilisation :
    // label_bbox = adjustBboxHeight(label_bbox, 40);
    // value_bbox = adjustBboxHeight(value_bbox, 40);

    displayPage(project_id, currentDocID, index, init_scroll);
    return true;
  } catch (error) {
    console.error("Erreur chargement des données OCR:", error);
    return false;
  }
}

// === DISPLAY IMAGE & BBOXES ===
function displayPage(project_id, document_id, index, init_scroll=false) {

  // Cherche l'image
  const imageElement = document.getElementById("page-image");
  imageElement.style.display = "none";
  if(svg!=null)
    svg.style.display = "none"; // Masquer au départ

  page_id = `page_${index+1}`;

  // Load image
  fetch(`/get_image/${project_id}/${document_id}/${page_id}.png`)
    .then(res => res.blob())
    .then(blob => {
      imageElement.src = URL.createObjectURL(blob);
    })
    .catch(err => {
      console.error("Image load failed:", err);
      imageElement.style.display = "none";
    });

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
    // Affichage des polygones avec couleurs par label
    displayAllBlocks(svg, all_blocks, 0, 0, scaleX, scaleY);
    displayAllGridCells(svg, grid_cells, 0, 0, scaleX, scaleY);
    displayBbox(svg, extract_values, label_bbox, 0, 0, scaleX, scaleY, "label");
    displayBbox(svg, extract_values, value_bbox, 0, 0, scaleX, scaleY, "value");
    // displayCheckedBoxes(svg, checked_boxes, 0, 0, scaleX, scaleY);

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

    // Effacer le tableau
    document.getElementById("table-container").innerHTML = "";
    // Génération du tableau éditable
    generateEditableTable(extract_values);
    // Pagination après le tableau
    createPaginationControls(currentPageIndex+1, nbrPageMax);


  };
  imageElement.onerror = () => {
    imageElement.style.display = "none";
    // Optionnel: afficher un message d’erreur
  };
}

// === DISPLAY ALL TESSERACT BLOCKS ===
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

// === DISPLAY BOXES ON IMAGE ===
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
      let fillColor = "rgba(200, 200, 200, 0)";
      let strokeColor = "none";
      let strokeWidth = 0;
      if (isListOfBoxes && boxType === "value") {
        fillColor = "rgba(255, 215, 0, 0.25)";   // gold tint
        strokeColor = "rgba(255, 140, 0, 0.9)";   // orange outline
        strokeWidth = 1.5;
      } else if (labelColors[label] && labelColors[label][boxType]) {
        fillColor = labelColors[label][boxType];
      }
      polygon.setAttribute("fill", fillColor);
      polygon.setAttribute("stroke", strokeColor);
      polygon.setAttribute("stroke-width", strokeWidth);
      polygon.setAttribute("title", label);

      const tooltipText = index !== null
        ? `${label}[${index}] = ${v ?? ""}`
        : `${label} = ${v ?? ""}`;

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
      tooltip.textContent = `Grille r${row} c${col}`;
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

// === DISPLAY CHECKED BOXES ===
function displayCheckedBoxes(svg, checkedCells, offsetX, offsetY, scaleX, scaleY) {
  if (!checkedCells || !checkedCells.length) return;

  checkedCells.forEach((cell) => {
    const bbox = cell.bbox;
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
    rect.setAttribute("stroke", "rgba(255, 152, 0, 0.95)");
    rect.setAttribute("stroke-width", "1.5");

    rect.addEventListener("mouseenter", (e) => {
      const row = (cell.row ?? "?");
      const col = (cell.col ?? "?");
      const ratio = (typeof cell.fill_ratio === "number") ? cell.fill_ratio : "n/a";
      tooltip.textContent = `Case cochée r${row} c${col} (ratio=${ratio})`;
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

// === PAGINATION ===
function createPaginationControls(current, max) {
  const container = document.createElement("div");
  container.className = "pagination-container";

  const prevBtn = document.createElement("button");
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
        loadPage(currentProjectID, val - 1);
      } else {
        pageInput.value = current;
      }
    }
  });
  //Add event when user change input
  pageInput.addEventListener("change", () => {
    let val = parseInt(pageInput.value);
    if (!isNaN(val) && val >= 1 && val <= max) {
      loadPage(currentProjectID, val - 1);
    } else {
      pageInput.value = current;
    }
  });

  const pageMaxText = document.createElement("span");
  pageMaxText.textContent = `/${max}`;
  pageDiv.append(pageText, pageInput, pageMaxText);
  
  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "btn btn-outline-primary btn-sm mx-1";
  nextBtn.innerHTML = '<i class="bi bi-chevron-right"></i>';
  nextBtn.onclick = nextPage;

  container.append(prevBtn, pageDiv, nextBtn);
  document.getElementById("table-container").appendChild(container);
}

function previousPage() {
  if (currentPageIndex <= 0) return;
  loadPage(currentProjectID, --currentPageIndex);
}

function nextPage() {
  if (currentPageIndex >= nbrPageMax-1) return;
  loadPage(currentProjectID, ++currentPageIndex);
}

// === TABLE UI ===
function generateEditableTable(data, containerId = "table-container") {
  const container = document.getElementById(containerId);
  if (!container) return;

  const table = document.createElement("table");
  table.className = "param-table";

  const thead = table.createTHead();
  const headerRow = thead.insertRow();
  ["Paramètre", "Valeur"].forEach(text => {
    const th = document.createElement("th");
    th.textContent = text;
    headerRow.appendChild(th);
  });

  const tbody = document.createElement("tbody");

  for (const [key, value] of Object.entries(data)) {
    const row = document.createElement("tr");

    const paramCell = document.createElement("td");
    paramCell.contentEditable = "false";
    paramCell.textContent = key;
    paramCell.dataset.originalKey = key;
    
    // Apply label color if available
    if (labelColors[key] && labelColors[key].label) {
      paramCell.style.backgroundColor = labelColors[key].label;
    }

    const valueCell = document.createElement("td");
    valueCell.contentEditable = "true";
    valueCell.textContent = value !== null ? value : "";

    paramCell.addEventListener("input", () => {
      const oldKey = paramCell.dataset.originalKey;
      const newKey = paramCell.textContent.trim();

      if (newKey && newKey !== oldKey && !(newKey in data)) {
        data[newKey] = data[oldKey];
        delete data[oldKey];
        paramCell.dataset.originalKey = newKey;
        sendTableToServer();
      }
    });

    valueCell.addEventListener("input", () => {
      const currentKey = paramCell.dataset.originalKey;
      data[currentKey] = valueCell.textContent.trim();
      sendTableToServer();
    });

    row.append(paramCell, valueCell);
    tbody.appendChild(row);
  }

  table.appendChild(tbody);
  container.appendChild(table);
}

// === SYNC TO SERVER ===
function sendTableToServer() {
  const table = document.querySelector(".param-table");
  if (!table) return;

  const data = {};
  table.querySelectorAll("tbody tr").forEach(row => {
    const cells = row.querySelectorAll("td");
    const key = cells[0].textContent.trim();
    const value = cells[1].textContent.trim();
    if (key) {
      data[key] = value;
      extract_values[key] = value;
    }
  });

  const formData = new FormData();
  formData.append("project_id", currentProjectID);
  formData.append("document_id", currentDocID);
  formData.append("filename", `table_page_${currentDocPage+1}.json`);
  formData.append("data", JSON.stringify(data));

  fetch("/put_data", { method: "POST", body: formData })
    .then(res => res.json())
    .then(console.log)
    .catch(err => console.error("Upload failed:", err));
}


// === ROTATE & ZOOM CALLBACKS ===
let currentRotation = 0;
let currentScale = 1;
const minScale = 0.2;
const maxScale = 3;

function initButtonCallback(){
  const btnRotate = document.getElementById('btn-rotate');
  const btnZoomIn = document.getElementById('btn-zoom-in');
  const btnZoomOut = document.getElementById('btn-zoom-out');
  const btnReset = document.getElementById('btn-reset');

  if (btnRotate) {
    btnRotate.addEventListener('click', () => {
      currentRotation = (currentRotation + 90) % 360;
      displayPage(currentProjectID, currentDocID, currentDocPage);
    });
  }
  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
      currentScale = Math.min(currentScale + 0.2, maxScale);
      displayPage(currentProjectID, currentDocID, currentDocPage);
    });
  }
  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
      currentScale = Math.max(currentScale - 0.2, minScale);
      displayPage(currentProjectID, currentDocID, currentDocPage);
    });
  }
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      currentRotation = 0;
      currentScale = 1;
      displayPage(currentProjectID, currentDocID, currentDocPage,true);
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
    createFileList(projectId, documentId, project_data);

    //Display First page
    await loadPage(projectId, 0,true);


    //display project data in fileList
    displayInfo(`📁 Fichier: ${project_data[0].filename}`);


  }
  else {
    displayInfo("📁 Fichier: Aucun fichier trouvé");
  }
  stopSpinner();

});

// Parcourt tous les bbox d'un objet (ex: label_bbox) et ajuste la hauteur si elle dépasse une valeur seuil
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


