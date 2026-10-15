import json
import os
import shutil
import threading
from pathlib import Path


try:
    from google.cloud import storage as gcs_storage
except Exception:
    gcs_storage = None


class StorageBackend:
    def __init__(self, local_root, mode="local", bucket_name=None, prefix="uploads"):
        self.local_root = os.path.abspath(local_root)
        self._mode = (mode or "local").strip().lower()
        self.bucket_name = (bucket_name or "").strip()
        self.prefix = (prefix or "uploads").strip().strip("/")
        self._lock = threading.Lock()

        if self._mode not in {"local", "gcs"}:
            raise ValueError("Invalid storage mode. Expected 'local' or 'gcs'.")

        self._gcs_client = None
        self._gcs_bucket = None
        if self._mode == "gcs":
            try:
                self._init_gcs()
            except Exception as exc:
                print(f"[storage_backend] GCS init failed ({exc}).")
                raise

    @property
    def mode(self):
        return self._mode

    @property
    def gcs_enabled(self):
        return gcs_storage is not None

    def _init_gcs(self):
        if gcs_storage is None:
            raise RuntimeError(
                "google-cloud-storage is required for GCS mode but is not installed."
            )
        if not self.bucket_name:
            raise RuntimeError("GCS mode requires GCS_BUCKET to be set.")
        self._gcs_client = gcs_storage.Client()
        self._gcs_bucket = self._gcs_client.bucket(self.bucket_name)
        if not self._gcs_bucket.exists():
            raise RuntimeError(f"GCS bucket '{self.bucket_name}' does not exist.")

    def set_mode(self, mode):
        normalized = (mode or "").strip().lower()
        if normalized not in {"local", "gcs"}:
            raise ValueError("Invalid storage mode. Expected 'local' or 'gcs'.")
        with self._lock:
            if normalized == self._mode:
                return
            if normalized == "gcs":
                self._init_gcs()
            self._mode = normalized

    def info(self):
        return {
            "mode": self._mode,
            "gcs_enabled": self.gcs_enabled,
            "bucket": self.bucket_name if self._mode == "gcs" else None,
            "prefix": self.prefix if self._mode == "gcs" else None,
        }

    def _blob_prefix(self, *parts):
        safe_parts = [str(p).strip("/\\") for p in parts if str(p).strip("/\\")]
        joined = "/".join(safe_parts)
        if self.prefix:
            return f"{self.prefix}/{joined}" if joined else self.prefix
        return joined

    def _local_dir(self, *parts):
        return os.path.join(self.local_root, *parts)

    def _local_document_is_cached(self, project_id, document_id):
        document_dir = self._local_dir(project_id, document_id)
        if not os.path.isdir(document_dir):
            return False
        if os.path.exists(os.path.join(document_dir, "info.json")):
            return True
        return any(os.path.isfile(os.path.join(root, name)) for root, _, files in os.walk(document_dir) for name in files)

    def hydrate_project(self, project_id):
        if self._mode != "gcs":
            return
        project_dir = self._local_dir(project_id)
        if os.path.isdir(project_dir) and any(os.scandir(project_dir)):
            return
        prefix = self._blob_prefix(project_id)
        os.makedirs(project_dir, exist_ok=True)
        for blob in self._gcs_client.list_blobs(self.bucket_name, prefix=f"{prefix}/"):
            rel_path = blob.name[len(prefix) + 1:]
            local_path = self._local_dir(project_id, *rel_path.split("/"))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            if os.path.exists(local_path):
                continue
            blob.download_to_filename(local_path)

    def get_project_documents(self, project_id):
        if self._mode == "gcs":
            project_prefix = self._blob_prefix(project_id)
            doc_ids = set()
            prefix = f"{project_prefix}/"

            for blob in self._gcs_client.list_blobs(self.bucket_name, prefix=prefix):
                rel = blob.name[len(prefix):] if blob.name.startswith(prefix) else blob.name
                parts = rel.split("/")
                if len(parts) < 2:
                    continue
                doc_id = parts[0].strip()
                if doc_id:
                    doc_ids.add(doc_id)

            documents = []
            for doc_id in sorted(doc_ids):
                info_blob = self._gcs_bucket.blob(self._blob_prefix(project_id, doc_id, "info.json"))
                payload = json.loads(info_blob.download_as_text())
                if isinstance(payload, dict):
                    documents.append(payload)
            return documents

        if not os.path.isdir(self._local_dir(project_id)):
            return []

        documents = []
        for doc_name in sorted(os.listdir(self._local_dir(project_id))):
            doc_path = self._local_dir(project_id, doc_name)
            info_path = os.path.join(doc_path, "info.json")
            if not os.path.isdir(doc_path) or not os.path.exists(info_path):
                continue
            try:
                with open(info_path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                if isinstance(payload, dict):
                    documents.append(payload)
            except Exception:
                continue
        return documents

    def hydrate_document(self, project_id, document_id):
        if self._mode != "gcs":
            return
        if self._local_document_is_cached(project_id, document_id):
            return
        prefix = self._blob_prefix(project_id, document_id)
        document_dir = self._local_dir(project_id, document_id)
        os.makedirs(document_dir, exist_ok=True)
        for blob in self._gcs_client.list_blobs(self.bucket_name, prefix=f"{prefix}/"):
            rel_path = blob.name[len(prefix) + 1:]
            if not rel_path:
                continue
            local_path = self._local_dir(project_id, document_id, *rel_path.split("/"))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            if os.path.exists(local_path):
                continue
            blob.download_to_filename(local_path)

    def sync_document(self, project_id, document_id):
        if self._mode != "gcs":
            return
        raise RuntimeError("Bucket syncing is disabled; this app stores documents locally only.")

    def delete_document(self, project_id, document_id):
        local_doc = self._local_dir(project_id, document_id)
        if os.path.exists(local_doc):
            shutil.rmtree(local_doc, ignore_errors=True)

        if self._mode == "gcs":
            prefix = self._blob_prefix(project_id, document_id)
            for blob in self._gcs_client.list_blobs(self.bucket_name, prefix=f"{prefix}/"):
                blob.delete()

    def delete_project(self, project_id):
        local_project = self._local_dir(project_id)
        if os.path.exists(local_project):
            shutil.rmtree(local_project, ignore_errors=True)

        if self._mode == "gcs":
            prefix = self._blob_prefix(project_id)
            for blob in self._gcs_client.list_blobs(self.bucket_name, prefix=f"{prefix}/"):
                blob.delete()

    def list_projects(self):
        if self._mode != "gcs":
            if not os.path.isdir(self.local_root):
                return []
            return [
                d for d in os.listdir(self.local_root)
                if os.path.isdir(self._local_dir(d))
            ]

        projects = set()
        prefix = f"{self.prefix}/" if self.prefix else ""
        for blob in self._gcs_client.list_blobs(self.bucket_name, prefix=prefix):
            rel = blob.name[len(prefix):] if prefix else blob.name
            parts = rel.split("/")
            if parts and parts[0]:
                projects.add(parts[0])
        return sorted(projects)
