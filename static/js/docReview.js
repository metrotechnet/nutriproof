// === GLOBAL STATE ===
let page_id = '';
let extract_values = {};
let label_bbox = {};
let value_bbox = {};

let currentDocPage = 0;
let currentDocID = 0;
let currentProjectID = "";
let currentPageIndex = 0;
let currentFileList = [];

let nbrPageMax = 0;
let project_data = null;
let padding = 200; // ou la valeur désirée
let svg = null

// Create different colors for each label with high contrast
const labelColors = {
  "Matricule": { label: "hsla(0, 85%, 45%, 0.4)", value: "hsla(0, 85%, 65%, 0.4)" },
  "Visite": { label: "hsla(120, 85%, 35%, 0.4)", value: "hsla(120, 85%, 55%, 0.4)" },
  "Temps": { label: "hsla(240, 85%, 45%, 0.4)", value: "hsla(240, 85%, 65%, 0.4)" },
  "Protéine C réactive": { label: "hsla(300, 85%, 40%, 0.4)", value: "hsla(300, 85%, 60%, 0.4)" },
  "Cholestérol total": { label: "hsla(30, 90%, 40%, 0.4)", value: "hsla(30, 90%, 60%, 0.4)" },
  "Triglycérides": { label: "hsla(180, 85%, 35%, 0.4)", value: "hsla(180, 85%, 55%, 0.4)" },
  "Cholestérol-HDL": { label: "hsla(270, 85%, 45%, 0.4)", value: "hsla(270, 85%, 65%, 0.4)" },
  "Cholestérol-LDL": { label: "hsla(60, 90%, 35%, 0.4)", value: "hsla(60, 90%, 55%, 0.4)" },
  "Cholestérol non-HDL": { label: "hsla(330, 85%, 40%, 0.4)", value: "hsla(330, 85%, 60%, 0.4)" },
  "Ratio Chol tot./Chol-HDL": { label: "hsla(150, 85%, 35%, 0.4)", value: "hsla(150, 85%, 55%, 0.4)" },
  "Glucose": { label: "hsla(210, 85%, 45%, 0.4)", value: "hsla(210, 85%, 65%, 0.4)" },
  "Insuline": { label: "hsla(45, 90%, 40%, 0.4)", value: "hsla(45, 90%, 60%, 0.4)" }
};

const tooltip = document.createElement("div");
tooltip.className = "tooltip";
document.body.appendChild(tooltip);

// === DISPLAY INFO ===
function displayInfo(info) {
  //display info in ocr-demo-title
  const title = document.getElementById("ocr-demo-title");
  title.innerHTML = `${info}<br><i style="font-size:0.5em;">Vérifier les valeurs de chaque page et appuyez sur Terminer</i>`;

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
        authFetch(`/get_data/${project_id}/${currentDocID}/label_bbox_${page_id}.json`).then(res => res.json()),
        authFetch(`/get_data/${project_id}/${currentDocID}/value_bbox_${page_id}.json`).then(res => res.json()),
        authFetch(`/get_data/${project_id}/${currentDocID}/table_${page_id}.json`).then(res => res.json())
    ]);
    if (!responses[0].data_string || !responses[1].data_string || !responses[2].data_string) {
        // Handle empty responses
      return false;
    }
    label_bbox = JSON.parse(responses[0].data_string || '{}');
    value_bbox = JSON.parse(responses[1].data_string || '{}');
    extract_values = JSON.parse(responses[2].data_string || '{}');
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

  // Load image via authFetch to include auth token
  authFetch(`/get_image/${project_id}/${document_id}/${page_id}.png`)
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
    displayBbox(svg, extract_values, label_bbox, 0, 0, scaleX, scaleY, "label");
    displayBbox(svg, extract_values, value_bbox, 0, 0, scaleX, scaleY, "value");

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
    // Création des contrôles de pagination
    createPaginationControls(currentPageIndex+1, nbrPageMax);
    // Génération du tableau éditable
    generateEditableTable(extract_values);


  };
  imageElement.onerror = () => {
    imageElement.style.display = "none";
    // Optionnel: afficher un message d’erreur
  };
}

// === DISPLAY BOXES ON IMAGE ===
function displayBbox(svg, data, boxes, offsetX,offsetY, scaleX, scaleY, boxType) {

  Object.entries(boxes).forEach(([label, bbox]) => {
    if (!bbox || bbox.length !== 4) return;
    const value = data[label];
    let x = bbox[0][0] * scaleX + offsetX;
    let y = bbox[0][1] * scaleY + offsetY;
    let w = Math.max(1, (bbox[1][0] - bbox[0][0]) * scaleX);
    let h = Math.max(1, (bbox[2][1] - bbox[1][1]) * scaleY);

    // Définir les 4 coins du rectangle (pas de rotation)
    let corners = [
      [x , y ], // haut gauche
      [x + w , y ], // haut droit
      [x + w , y + h ], // bas droit
      [x , y + h ] // bas gauche
    ];

    let polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    polygon.setAttribute("points", corners.map(([px, py]) => `${px},${py}`).join(" "));
    polygon.setAttribute("class", "bbox");
    
    // Use label-specific color if available, otherwise use default
    let fillColor = "rgba(200, 200, 200, 0.3)"; // default gray
    if (labelColors[label] && labelColors[label][boxType]) {
      fillColor = labelColors[label][boxType];
    }
    polygon.setAttribute("fill", fillColor);
    polygon.setAttribute("title", label);

    polygon.addEventListener("mouseenter", (e) => {
      tooltip.textContent = `${label} = ${value}`;
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

  authFetch("/put_data", { method: "POST", body: formData })
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


