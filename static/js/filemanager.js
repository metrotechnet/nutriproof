let projectId = 'main';
let selectedCategory = null; // chosen by the user before each upload

// Available form types (category key -> display label), populated from /get_form_types
let FORM_TYPES = {};

// Chargement des projets (initialisation)
window.addEventListener('DOMContentLoaded', async function () {
    startSpinner("Chargement des projets...");
    try {
        const res = await fetch('/get_form_types');
        if (res.ok) FORM_TYPES = await res.json();
    } catch (e) { /* keep empty fallback */ }
    await loadProjects();
    stopSpinner();
});

// Ask the user which form type they are about to upload.
async function askFormType() {
    const inputOptions = {};
    for (const [key, label] of Object.entries(FORM_TYPES)) {
        inputOptions[key] = label;
    }
    const { value: choice } = await Swal.fire({
        title: 'Type de formulaire',
        text: "S\u00e9lectionnez le type de document avant de choisir le fichier.",
        input: 'select',
        inputOptions,
        inputPlaceholder: 'Choisir un type...',
        showCancelButton: true,
        confirmButtonText: 'Continuer',
        cancelButtonText: 'Annuler',
        inputValidator: (value) => {
            if (!value) return 'Veuillez choisir un type de formulaire';
        }
    });
    return choice || null;
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
// Arrêter le spinner
function stopSpinner() {
    Swal.close();
}

function parseProjectDate(value) {
    if (!value || value === '-') return null;

    // Try native parsing first (ISO and common RFC formats).
    const direct = new Date(value);
    if (!Number.isNaN(direct.getTime())) return direct;

    // Fallback for dd/mm/yyyy[ hh:mm[:ss]] style.
    const m = String(value).trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$/);
    if (!m) return null;

    let day = Number(m[1]);
    let month = Number(m[2]) - 1;
    let year = Number(m[3]);
    const hour = Number(m[4] || 0);
    const minute = Number(m[5] || 0);
    const second = Number(m[6] || 0);

    if (year < 100) year += 2000;
    const parsed = new Date(year, month, day, hour, minute, second);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

// Nouveau fichier pour le projet projectId
const btnNewFile = document.getElementById('btn-new-file');
const btnExportFiles = document.getElementById('btn-export-files');
const btnDeleteSelected = document.getElementById('btn-delete-selected');
const fileBrowserMain = document.getElementById('file-browser-main');
const selectAllDocuments = document.getElementById('select-all-documents');

function updateSelectAllState() {
    if (!selectAllDocuments) return;
    const selectableRows = Array.from(document.querySelectorAll('.row-select:not(:disabled)'));
    if (!selectableRows.length) {
        selectAllDocuments.checked = false;
        selectAllDocuments.indeterminate = false;
        return;
    }
    const selectedRows = selectableRows.filter((checkbox) => checkbox.checked).length;
    selectAllDocuments.checked = selectedRows === selectableRows.length;
    selectAllDocuments.indeterminate = selectedRows > 0 && selectedRows < selectableRows.length;
}

if (selectAllDocuments) {
    selectAllDocuments.addEventListener('change', function () {
        const checked = this.checked;
        const rowCheckboxes = document.querySelectorAll('.row-select:not(:disabled)');
        rowCheckboxes.forEach((checkbox) => {
            checkbox.checked = checked;
        });
        updateSelectAllState();
    });
}

if (btnExportFiles) {
    btnExportFiles.addEventListener('click', async () => {
        const selectedRows = Array.from(document.querySelectorAll('.row-select:checked:not(:disabled)'));
        if (!selectedRows.length) {
            Swal.fire('Exportation', 'Sélectionnez au moins un document à exporter.', 'info');
            return;
        }

        const selectedDocuments = selectedRows
            .map((rowCheckbox) => ({
                document_id: rowCheckbox.dataset.documentId || '',
                nbr_pages: rowCheckbox.dataset.nbrPages || '',
                category: rowCheckbox.dataset.category || '',
            }))
            .filter((doc) => doc.document_id && doc.nbr_pages);

        if (!selectedDocuments.length) {
            Swal.fire('Exportation', 'Aucun document valide à exporter.', 'warning');
            return;
        }

        const categories = [...new Set(selectedDocuments.map((doc) => doc.category).filter(Boolean))];
        if (categories.length > 1) {
            const conflictTypes = categories
                .map((categoryKey) => FORM_TYPES[categoryKey] || categoryKey)
                .join(', ');
            Swal.fire(
                'Erreur',
                `Tous les documents sélectionnés doivent être du même type pour être exportés ensemble.\n\nTypes détectés : ${conflictTypes}`,
                'error'
            );
            return;
        }

        await exportAllSelectedDocuments(projectId, selectedDocuments, categories[0] || '');
    });
}

if (btnDeleteSelected) {
    btnDeleteSelected.addEventListener('click', async () => {
        const selectedRows = Array.from(document.querySelectorAll('.row-select:checked:not(:disabled)'));
        if (!selectedRows.length) {
            Swal.fire('Suppression', "Aucun document n'est sélectionné.", 'error');
            return;
        }

        const selectedDocumentIds = [...new Set(
            selectedRows
                .map((rowCheckbox) => rowCheckbox.dataset.documentId || '')
                .filter(Boolean)
        )];

        if (!selectedDocumentIds.length) {
            Swal.fire('Suppression', "Aucun document valide n'est sélectionné.", 'error');
            return;
        }

        const confirmation = await Swal.fire({
            title: 'Confirmer la suppression',
            text: `Voulez-vous vraiment supprimer les ${selectedDocumentIds.length} documents sélectionnés ?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Oui, supprimer',
            cancelButtonText: 'Annuler'
        });
        if (!confirmation.isConfirmed) return;

        const failedDocuments = [];
        startSpinner('Suppression en cours...');
        try {
            for (const documentId of selectedDocumentIds) {
                try {
                    await ProjectManager.deleteDocument(projectId, documentId);
                } catch (err) {
                    failedDocuments.push(documentId);
                }
            }
            await loadProjects();
        } finally {
            stopSpinner();
        }

        if (failedDocuments.length) {
            Swal.fire('Suppression partielle', `Certains documents n'ont pas pu être supprimés : ${failedDocuments.join(', ')}`, 'warning');
            return;
        }
        Swal.fire('Suppression terminée', 'Les documents sélectionnés ont été supprimés.', 'success');
    });
}

btnNewFile.addEventListener('click', async () => {
    const choice = await askFormType();
    if (!choice) return;
    selectedCategory = choice;
    fileBrowserMain.value = '';
    fileBrowserMain.click();
}); 

// Gestion du changement de fichier
fileBrowserMain.addEventListener('change', async (event) => {
    const files = event.target.files;
    startSpinner("Chargement en cours...");
    if (!files || files.length === 0) { stopSpinner(); return; }
    for (const file of files) {
        const ok = await window.addFileToProject({ target: { files: [file] } }, projectId);
        if (!ok) break;
    }
    stopSpinner();
});

document.addEventListener('change', (event) => {
    if (event.target && event.target.classList && event.target.classList.contains('row-select')) {
        updateSelectAllState();
    }
});


// Utilitaire pour afficher le tableau des projets
async function loadProjects() {
    const tableBody = document.querySelector('#projects-table tbody');
    tableBody.innerHTML = '';
    const data = await ProjectManager.listProjects();
    if (!Array.isArray(data) || !data.length) {
        updateSelectAllState();
        return;
    }
    // On affiche chaque fichier du projet projectId sur une ligne
    const mainProjectId = projectId;
    const mainDetails = await ProjectManager.getProject(mainProjectId);
    if(mainDetails && mainDetails.length) {
        const sortedDetails = [...mainDetails].sort((a, b) => {
            const da = parseProjectDate(a?.upload_date);
            const db = parseProjectDate(b?.upload_date);
            const ta = da ? da.getTime() : 0;
            const tb = db ? db.getTime() : 0;
            if (ta !== tb) return ta - tb; // oldest first
            return String(a?.document_id || '').localeCompare(String(b?.document_id || ''));
        });

        for (const file of sortedDetails) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="align-middle text-center"><input type="checkbox" class="form-check-input row-select" data-document-id="${file.document_id || ''}" data-nbr-pages="${file.nbr_pages || ''}" data-category="${file.category || ''}"></td>
                <td class="align-middle text-center" data-col="document-id">${file.document_id || '-'}</td>
                <td class="align-middle text-center">${file.filename || '-'}</td>
                <td class="align-middle text-center">${FORM_TYPES[file.category] || file.category || '-'}</td>
                <td class="align-middle text-center">${file.upload_date || '-'}</td>
                <td class="align-middle text-center">${file.nbr_pages || '-'}</td>
                <td class="align-middle text-center"><button class="btn btn-primary btn-sm" onclick="viewProject(projectId,'${file.document_id}')"><i class="fas fa-eye"></i></button></td>
                <td class="align-middle text-center" data-col="status"><span class="badge px-3 py-2 bg-info" style="display:inline-block;width:120px;">Lecture</span></td>
                <td class="align-middle text-center"><input type="checkbox" class="form-check-input" name="v1-${file.document_id}" ${file.v1=='true' ? 'checked' : ''} onchange="verifyDocument('${projectId}','${file.document_id}','v1',this.checked ? 'true' : 'false')"></td>
                <td class="align-middle text-center"><input type="checkbox" class="form-check-input" name="v2-${file.document_id}" ${file.v2=='true' ? 'checked' : ''} onchange="verifyDocument('${projectId}','${file.document_id}','v2',this.checked ? 'true' : 'false')"></td>

            `;
            tableBody.appendChild(tr);
            //start polling et mise à jour du status
            pollJob(file.document_id);
        }
    }
    updateSelectAllState();
    return;
}

//Send verification request
window.verifyDocument = function(projectId, documentId,label,validFlag) {
    //put data in form
    const formData = new FormData();
    formData.append("projectName", projectId);
    formData.append("documentID", documentId);
    formData.append("label", label);
    formData.append("value", validFlag);

    fetch(`/validate_document/`, { 
        method: 'POST', 
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        return response.json();
    })
    .then(data => {
        console.log("Document validation response:", data);
    })
    .catch(err => {
        console.error("Document validation failed:", err);
    });
};

// Ouvrir le projet dans un nouvel onglet
window.viewProject = function(projectId,documentId) {
    window.location.href = `review?project=${projectId}&document=${documentId}`;
};

// Effacer document avec confirmation
window.deleteDocumentConfirm = async function(documentId) {
    const result = await Swal.fire({
        title: 'Confirmer la suppression',
        text: `Voulez-vous vraiment supprimer ce document ?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Oui, supprimer',
        cancelButtonText: 'Annuler'
    });
    if (result.isConfirmed) {
        try {
            startSpinner('Suppression en cours...');
            await ProjectManager.deleteDocument(projectId, documentId);
            await loadProjects();
            stopSpinner();
        } catch (e) {
            Swal.fire('Erreur', e.message || 'Suppression impossible', 'error');
        }
    }
};

// Ajout de fichier au projet
window.addFileToProject = async function(event, projectId) {
    const file = event.target.files[0];
    if (!file) return false;
    if (!selectedCategory) {
        Swal.fire('Erreur', 'Type de formulaire non s\u00e9lectionn\u00e9.', 'error');
        return false;
    }
  //Upload file
  const uploadResults = await OcrManager.sendOCRFile(projectId, file, selectedCategory);
  if (!uploadResults[0]) return false;

  //start processing
  const jobid = await OcrManager.processOCRFile(projectId, uploadResults[0], uploadResults[1], 0, file.name, selectedCategory);

  // Add a placeholder row at the end of the table immediately
  const tableBody = document.querySelector('#projects-table tbody');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="align-middle text-center"><input type="checkbox" class="form-check-input row-select" disabled></td>
    <td class="align-middle text-center" data-col="document-id">${jobid}</td>
    <td class="align-middle text-center">${file.name}</td>
    <td class="align-middle text-center">${FORM_TYPES[selectedCategory] || selectedCategory || '-'}</td>
    <td class="align-middle text-center">-</td>
    <td class="align-middle text-center">-</td>
    <td class="align-middle text-center"><button class="btn btn-primary btn-sm" disabled><i class="fas fa-eye"></i></button></td>
    <td class="align-middle text-center" data-col="status"><span class="badge px-3 py-2 bg-info" style="display:inline-block;width:120px;">En cours</span></td>
    <td class="align-middle text-center"><input type="checkbox" class="form-check-input" disabled></td>
    <td class="align-middle text-center"><input type="checkbox" class="form-check-input" disabled></td>
  `;
  tableBody.appendChild(tr);
  updateSelectAllState();

  //start polling et mise à jour du status
  pollJob(jobid);
  return true;
};

//Disable line in table
function disableLine(jobId) {
    const tableBody = document.querySelector('#projects-table tbody');
    const rows = tableBody.querySelectorAll('tr');
    for (const row of rows) {
        const idCell = row.querySelector('td[data-col="document-id"]');
        if (idCell && idCell.textContent === jobId) {
            // Désactive tous les boutons de la ligne
            const buttons = row.querySelectorAll('button');
            buttons.forEach(btn => btn.disabled = true);
            // Désactive aussi les cases à cocher
            const checkboxes = row.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => cb.disabled = true);
            // Ajoute le style grisé au badge de status
            const statusCell = row.querySelector('td[data-col="status"] span');
            if (statusCell) {
                statusCell.classList.add('text-muted');
            }
        }
    }
    updateSelectAllState();
}
//Enable line in table
function enableLine(jobId) {
    const tableBody = document.querySelector('#projects-table tbody');
    const rows = tableBody.querySelectorAll('tr');
    for (const row of rows) {
        const idCell = row.querySelector('td[data-col="document-id"]');
        if (idCell && idCell.textContent === jobId) {
            // Réactive tous les boutons de la ligne
            const buttons = row.querySelectorAll('button');
            buttons.forEach(btn => btn.disabled = false);
            // Réactive aussi les cases à cocher
            const checkboxes = row.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => cb.disabled = false);
            // Retire le style grisé au badge de status
            const statusCell = row.querySelector('td[data-col="status"] span');
            if (statusCell) {
                statusCell.classList.remove('text-muted');
            }
        }
    }
    updateSelectAllState();
}

// Annuler un job OCR
window.cancelOCRJob = async function(jobId) {
    try {
        await OcrManager.cancelOCR(jobId);
    } catch (err) {
        console.error('Cancel failed:', err);
    }
};

// Fonction de polling pour vérifier l'état d'un job
async function pollJob(jobId) {
    // === Polling Task ===
    status_map = {
        "completed": "Terminé",
        "running": "En cours",
        "cancelled": "Annulé",
        "not_found": "Terminé"
    };
    disableLine(jobId);

    let iterationCount = 0; // Compteur d'itérations
    const intervalId = setInterval(() => {
        pollStatusAsync(iterationCount);
        iterationCount++;
    }, 1000);

    async function pollStatusAsync(iterationCount) {

        try {
            const status_data = await OcrManager.checkStatus(jobId);

            if (status_data && status_data.status) {
                // Met à jour le badge de status dans la colonne du projet
                const tableBody = document.querySelector('#projects-table tbody');
                const rows = tableBody.querySelectorAll('tr');
                for (const row of rows) {
                    const idCell = row.querySelector('td[data-col="document-id"]');
                    if (idCell && idCell.textContent === jobId) {
                        const statusCell = row.querySelector('td[data-col="status"]');
                        if (statusCell) {
                            if(status_data.status=='running') {
                                statusCell.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;gap:6px;"><span class="badge px-3 py-2 bg-warning">${status_data.progress}</span><button class="btn btn-sm btn-outline-danger" onclick="cancelOCRJob('${jobId}')" title="Annuler"><i class="fas fa-times"></i></button></div>`;
                            } else {
                                const bgClass = status_data.status === 'completed' ? 'success' : (status_data.status === 'cancelled' ? 'secondary' : 'info');
                                statusCell.innerHTML = `<span class="badge px-3 py-2 bg-${bgClass}" style="display:inline-block;width:120px;">${status_map[status_data.status] || status_data.status}</span>`;
                            }
                        }
                        // On arrête le polling si terminé ou annulé
                        if (status_data.status === 'completed' || status_data.status === 'cancelled') {
                            enableLine(jobId);
                            clearInterval(intervalId);
                            // Update the placeholder row with actual server data
                            if (status_data.status === 'completed') {
                                try {
                                    const details = await ProjectManager.getProject(projectId);
                                    if (Array.isArray(details)) {
                                        const file = details.find(f => f.document_id === jobId);
                                        if (file) {
                                            const tbody = document.querySelector('#projects-table tbody');
                                            for (const row of tbody.querySelectorAll('tr')) {
                                                if (row.querySelector('td[data-col="document-id"]')?.textContent.trim() === jobId) {
                                                    row.innerHTML = `
                                                        <td class="align-middle text-center"><input type="checkbox" class="form-check-input row-select" data-document-id="${file.document_id || ''}" data-nbr-pages="${file.nbr_pages || ''}" data-category="${file.category || ''}"></td>
                                                        <td class="align-middle text-center" data-col="document-id">${file.document_id || '-'}</td>
                                                        <td class="align-middle text-center">${file.filename || '-'}</td>
                                                        <td class="align-middle text-center">${FORM_TYPES[file.category] || file.category || '-'}</td>
                                                        <td class="align-middle text-center">${file.upload_date || '-'}</td>
                                                        <td class="align-middle text-center">${file.nbr_pages || '-'}</td>
                                                        <td class="align-middle text-center"><button class="btn btn-primary btn-sm" onclick="viewProject(projectId,'${file.document_id}')"><i class="fas fa-eye"></i></button></td>
                                                        <td class="align-middle text-center" data-col="status"><span class="badge px-3 py-2 bg-success" style="display:inline-block;width:120px;">Terminé</span></td>
                                                        <td class="align-middle text-center"><input type="checkbox" class="form-check-input" name="v1-${file.document_id}" ${file.v1=='true' ? 'checked' : ''} onchange="verifyDocument('${projectId}','${file.document_id}','v1',this.checked ? 'true' : 'false')"></td>
                                                        <td class="align-middle text-center"><input type="checkbox" class="form-check-input" name="v2-${file.document_id}" ${file.v2=='true' ? 'checked' : ''} onchange="verifyDocument('${projectId}','${file.document_id}','v2',this.checked ? 'true' : 'false')"></td>
                                                    `;
                                                    updateSelectAllState();
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                } catch (e) { /* ignore */ }
                            }
                            return;
                        }
                    }
                }
            }

        } catch (err) {
            enableLine(jobId);
            clearInterval(intervalId);
        }
    }
}

// === DOWNLOAD FINAL xls ===
async function downloadXlsFile(projectId, documentId, nbrPages, options = {}) {
    if (!documentId) {
        alert("No document loaded");
        return false;
    }
    const showSpinner = options.showSpinner !== false;
    let success = false;

    try {
        if (showSpinner) startSpinner('Téléchargement en cours...');

        let category = null;
        try {
            const projectDetails = await ProjectManager.getProject(projectId);
            if (Array.isArray(projectDetails)) {
                const file = projectDetails.find(item => item.document_id === documentId);
                category = file && file.category ? String(file.category) : null;
            }
        } catch (e) {
            category = null;
        }

        const endpoint = category === 'formulaire_suivi' ? '/download_xls_formulaire_suivi' : '/download_xls';
        const formData = new FormData();
        formData.append("project_id", projectId);
        formData.append("document_id", documentId);
        formData.append("nbr_pages", nbrPages);

        const response = await fetch(endpoint, { method: 'POST', body: formData });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

        const blob = await response.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = documentId + ".xls";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        success = true;
    } catch (err) {
        console.error("CSV export failed:", err);
        alert("Échec du téléchargement du fichier CSV.");
    } finally {
        if (showSpinner) stopSpinner();
    }
    return success;
}

async function exportAllSelectedDocuments(projectId, documents, category) {
    startSpinner('Exportation en cours...');
    try {
        const response = await fetch('/export_all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: projectId,
                category,
                documents,
            }),
        });

        if (!response.ok) {
            let errorMessage = `HTTP error! Status: ${response.status}`;
            try {
                const payload = await response.json();
                if (payload && payload.error) errorMessage = payload.error;
            } catch (e) {
                // Keep default message when response body is not JSON.
            }
            throw new Error(errorMessage);
        }

        const blob = await response.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        const stamp = new Date().toISOString().replace(/[:.]/g, '-');
        a.download = `export_all_${stamp}.xls`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        Swal.fire('Exportation terminée', 'Le fichier consolidé a été généré.', 'success');
    } catch (err) {
        console.error("Bulk export failed:", err);
        Swal.fire('Erreur', err.message || "Échec de l'exportation groupée.", 'error');
    } finally {
        stopSpinner();
    }
}
