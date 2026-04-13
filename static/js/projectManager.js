class ProjectManager {

  // Liste les projets
  static async listProjects() {
    try {
      const response = await authFetch('/list_projects', { method: 'GET' });
      const data = await response.json();
      if (data.error) {
        console.error("Error listing projects:", data.error);
      } else {
        console.log("Projects listed successfully:", data);
      }
      return data;
    } catch (error) {
      console.error("Error:", error);
      throw error;
    }
  }

  // Récupération des informations d'un projet
  static async getProject(project_id) {
    try {
      const formData = new FormData();
      formData.append("project_id", project_id);
      const response = await authFetch('/get_project', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (data.error) {
        console.error("Error loading project:", data.error);
        return null
      } else {
        console.log("Project loaded successfully:", data);
      }
      return data;
    } catch (error) {
      console.error("Error:", error);
      throw error;
    }
  }

  // Création d'un projet
  static async createProject(projectId) {
    try {
      const formData = new FormData();
      formData.append("project_id", projectId);
      const response = await authFetch('/create_project', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (data.error) {
        console.error("Error creating project:", data.error);
        Swal.fire({
          icon: 'error',
          title: 'Erreur création projet',
          text: data.error
        });
      } else {
        console.log("Project created successfully:", data);
      }
      return data;
    } catch (error) {
      console.error("Error:", error);
      throw error;
    }
  }

  // Suppression d'un projet
  static async deleteProject(projectId) {
    try {
      const formData = new FormData();
      formData.append("project_id", projectId);
      const response = await authFetch('/delete_project', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (data.error) {
        console.error("Error deleting project:", data.error);
        Swal.fire({
          icon: 'error',
          title: 'Erreur suppression projet',
          text: data.error
        });
      } else {
        console.log("Project deleted successfully:", data);
      }
      return data;
    } catch (error) {
      console.error("Error:", error);
      throw error;
    }
  }
    // Supprime un dossier document dans un projet via document_id
  static async deleteDocument(projectId, documentId) {
    const formData = new FormData();
    formData.append("project_id", projectId);
    formData.append("document_id", documentId);
    const response = await authFetch('/delete_document', {
      method: 'POST',
      body: formData
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Erreur lors de la suppression du dossier document');
    return data;
  }
}
