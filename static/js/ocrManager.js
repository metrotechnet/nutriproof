class OcrManager {
  // Envoi d'un fichier pour traitement OCR
  static async sendOCRFile(projectName, file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("projectName", projectName);

    const response = await authFetch('/upload_pdf', {
      method: 'POST',
      body: formData,
    });

    const result = await response.json();
    if (result.message == 'ok') {
      return [result.document_id, result.nbr_pages];
    } else {
      Swal.fire('Erreur', 'Impossible de télécharger le fichier', result.message);
      return [null, 0];
    }
  }
  // Envoi d'un fichier pour traitement OCR
  static async processOCRFile(projectName, document_id, nbr_pages, start_page, filename) {
    const formData = new FormData();
    formData.append("fileName", filename);
    formData.append("projectName", projectName);
    formData.append("documentID", document_id);
    formData.append("nbrPages", nbr_pages);
    formData.append("startPage", start_page);

    const response = await authFetch('/process_ocr', {
      method: 'POST',
      body: formData,
    });

    const result = await response.json();
    const jobId = result.job_id;

    if (!jobId) {
      Swal.fire('Erreur', 'Impossible de démarrer la tâche', 'error');
      return null;
    }
    return jobId;
  }

  // Vérification de l'état d'une tâche
  static async checkStatus(jobId) {
    const statusRes = await authFetch(`/status/${jobId}`);
    const statusData = await statusRes.json();

    const status = statusData.status;
    const progress = statusData.progress || '';
    //console.log(`Status: ${status}, Progress: ${progress}`);
    switch (status) {
      case 'running':
        return { message: `<i class='fas fa-spinner fa-spin'></i> En cours de traitement...`, "status": 'running', "progress": progress };
      case 'completed':
        return { message: `✅ Traitement terminé`, "status": 'completed', "progress": progress };
      case 'cancelled':
        return { message: `❌ Traitement annulé`, "status": "cancelled", "progress": progress };
      case 'failed':
        return { message: `❌ Erreur lors du traitement`, "status": 'failed', "progress": progress };
      case 'not_found':
        return { message: `❌ Document non trouvé`, "status": 'completed', "progress": progress };
    }
  }
}
