let projectId = 'main';

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

// Chargement des projets (initialisation)
window.addEventListener('DOMContentLoaded', async function () {
    // Chargement initial
    startSpinner("Chargement des projets...");
    await loadProjects();
    stopSpinner();
});

// Nouveau fichier pour le projet projectId
const btnNewFile = document.getElementById('btn-new-file');
const fileBrowserMain = document.getElementById('file-browser-main');
btnNewFile.addEventListener('click', () => {
    fileBrowserMain.value = '';
    fileBrowserMain.click();
}); 

// Gestion du changement de fichier
fileBrowserMain.addEventListener('change', async (event) => {
    const files = event.target.files;
    startSpinner("Chargement des projets...");
    if (!files || files.length === 0) return;
    for (const file of files) {
        await window.addFileToProject({ target: { files: [file] } }, projectId);
    }
    await loadProjects();
    stopSpinner();
});


// Utilitaire pour afficher le tableau des projets
async function loadProjects() {
    const tableBody = document.querySelector('#projects-table tbody');
    tableBody.innerHTML = '';
    const data = await ProjectManager.listProjects();
    if (!Array.isArray(data) || !data.length) {
        return;
    }
    // On affiche chaque fichier du projet projectId sur une ligne
    const mainProjectId = projectId;
    const mainDetails = await ProjectManager.getProject(mainProjectId);
    if(mainDetails && mainDetails.length) {
        for (const file of mainDetails) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="align-middle text-center">${file.document_id || '-'}</td>
                <td class="align-middle text-center">${file.filename || '-'}</td>
                <td class="align-middle text-center">${file.upload_date || '-'}</td>
                <td class="align-middle text-center">${file.nbr_pages || '-'}</td>
                <td class="align-middle text-center"><button class="btn btn-primary btn-sm" onclick="viewProject(projectId,'${file.document_id}')"><i class="fas fa-eye"></i></button></td>
                <td class="align-middle text-center"><button class="btn btn-success btn-sm" onclick="downloadXlsFile(projectId,'${file.document_id}','${file.nbr_pages}')"><i class="fas fa-download"></i></button></td>
                <td class="align-middle text-center"><button class="btn btn-danger btn-sm" onclick="deleteDocumentConfirm('${file.document_id}')"><i class="fas fa-trash"></i></button></td>
                <td class="align-middle text-center"><span class="badge w-100 px-3 py-2 bg-info" style="min-width: 120px;">Lecture</span></td>
                <td class="align-middle text-center"><input type="checkbox" class="form-check-input" name="v1-${file.document_id}" ${file.v1=='true' ? 'checked' : ''} onchange="verifyDocument('${projectId}','${file.document_id}','v1',this.checked ? 'true' : 'false')"></td>
                <td class="align-middle text-center"><input type="checkbox" class="form-check-input" name="v2-${file.document_id}" ${file.v2=='true' ? 'checked' : ''} onchange="verifyDocument('${projectId}','${file.document_id}','v2',this.checked ? 'true' : 'false')"></td>

            `;
            tableBody.appendChild(tr);
            //start polling et mise à jour du status
            pollJob(file.document_id);
        }
    }
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

    authFetch(`/validate_document/`, { 
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
    if (!file) return;
  //Upload file
  const uploadResults = await OcrManager.sendOCRFile(projectId, file);

  //start processing
  const jobid = await OcrManager.processOCRFile(projectId, uploadResults[0], uploadResults[1], 0, file.name);
  //start polling et mise à jour du status
  pollJob(jobid);

};

//Disable line in table
function disableLine(jobId) {
    const tableBody = document.querySelector('#projects-table tbody');
    const rows = tableBody.querySelectorAll('tr');
    for (const row of rows) {
        const idCell = row.querySelector('td');
        if (idCell && idCell.textContent === jobId) {
            // Désactive tous les boutons de la ligne
            const buttons = row.querySelectorAll('button');
            buttons.forEach(btn => btn.disabled = true);
            // Désactive aussi les cases à cocher
            const checkboxes = row.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => cb.disabled = true);
            // Ajoute le style grisé au badge de status
            const statusCell = row.querySelector('td:nth-child(8) span');
            if (statusCell) {
                statusCell.classList.add('text-muted');
            }
        }
    }
}
//Enable line in table
function enableLine(jobId) {
    const tableBody = document.querySelector('#projects-table tbody');
    const rows = tableBody.querySelectorAll('tr');
    for (const row of rows) {
        const idCell = row.querySelector('td');
        if (idCell && idCell.textContent === jobId) {
            // Réactive tous les boutons de la ligne
            const buttons = row.querySelectorAll('button');
            buttons.forEach(btn => btn.disabled = false);
            // Réactive aussi les cases à cocher
            const checkboxes = row.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => cb.disabled = false);
            // Retire le style grisé au badge de status
            const statusCell = row.querySelector('td:nth-child(8) span');
            if (statusCell) {
                statusCell.classList.remove('text-muted');
            }
        }
    }
}

// Fonction de polling pour vérifier l'état d'un job
async function pollJob(jobId) {
    // === Polling Task ===
    status_map = {
        "completed": "Terminé",
        "running": "En cours",
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
                    const idCell = row.querySelector('td');
                    if (idCell && idCell.textContent === jobId) {
                        // La colonne status est la 8ème (index 7)
                        const statusCell = row.querySelector('td:nth-child(8) span');
                        if (statusCell) {
                            if(status_data.status=='running')
                                statusCell.textContent = status_data.progress ;
                            else 
                                statusCell.textContent = status_map[status_data.status] ;
                            statusCell.className = 'badge w-100 px-3 py-2 bg-' + (status_data.status === 'completed' ? 'success' : 'warning');
                        }
                        // On arrête le polling si terminé
                        if (status_data.status === 'completed' ) {
                            enableLine(jobId);
                            clearInterval(intervalId);
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
function downloadXlsFile(projectId, documentId,nbrPages) {
    if (!documentId) {
        alert("No document loaded");
        return;
    }
    startSpinner('Téléchargement en cours...');
    const formData = new FormData();
    formData.append("project_id", projectId);
    formData.append("document_id", documentId);
    formData.append("nbr_pages", nbrPages);

    authFetch('/download_xls', { method: 'POST', body: formData })
        .then(response => {
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            return response.blob();
        })
        .then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = documentId+".xls";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        })
        .catch(err => {
            console.error("CSV export failed:", err);
            alert("Échec du téléchargement du fichier CSV.");
        }).finally(() => {
            stopSpinner();
        });
}
