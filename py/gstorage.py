import io
from typing import List, Optional
import mimetypes
import os

from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError


class GSStorage:
    

    def __init__(self, local_folder="uploads", bucket_name="nutriss-dbase"):
        """
        Initialize the GCS client and set the bucket.

        Args:
            bucket_name (str): Google Cloud Storage bucket name.
        """
        self.client = storage.Client()
        self.bucket_name = bucket_name
        self.bucket = self.client.bucket(bucket_name)
        self.local_folder = local_folder

    def upload_file(self, file_path: str) -> str:
        """
        Uploads a file to GCS.

        Args:
            source_dir (str): Local directory containing the source file.
            local_file_path (str): Local path to the source file.
            destination_blob_name (str): Destination blob name in GCS.
        """

        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            #Replace back slash
            destination_blob_name = file_path.replace("\\", "/")
            blob = self.bucket.blob(destination_blob_name)
            blob.cache_control = "no-cache"
            blob.content_type = mime_type
            blob.upload_from_filename(file_path)
            blob.patch()
            print(f"📤 Upload: {file_path} → {file_path}")
            return blob.public_url
        except Exception as e:
            raise RuntimeError(f"Erreur lors de l'upload : {str(e)}")

    def copy_file(self, source_blob_name: str, destination_blob_name: str):
        """
        Copies a blob within the same bucket.

        Args:
            source_blob_name (str): Path of the source blob.
            destination_blob_name (str): Destination blob path.
        """
        try:
            source_blob_name = source_blob_name.replace("\\", "/")
            source_blob = self.bucket.blob(source_blob_name)
            self.bucket.copy_blob(source_blob, self.bucket, destination_blob_name)
        except GoogleAPIError as e:
            raise RuntimeError(f"Erreur lors de la copie GCS : {str(e)}")

    def download_file(self, source_blob_name: str):
        """
        Downloads a blob to a local file.

        Args:
            source_blob_name (str): Name of the blob to download.
            destination_file_path (str): Local destination path.
        """
        try:
            source_blob_name = source_blob_name.replace("\\", "/")
            blob = self.bucket.blob(source_blob_name)
            blob.download_to_filename(source_blob_name)
            print(f"📥 Fichier téléchargé vers {source_blob_name}")
        except Exception as e:
            raise RuntimeError(f"Erreur lors du téléchargement : {str(e)}")
        
    # Create a folder
    def create_folder(self, folder_name: str):
        """
        Creates a folder (prefix) in the GCS bucket.

        Args:
            folder_name (str): Name of the folder to create.
        """
        try:
            folder_name = folder_name.replace("\\", "/")
            blob = self.bucket.blob(folder_name + "/")
            blob.upload_from_string("")
            print(f"📁 Dossier créé : {folder_name}")
        except Exception as e:
            raise RuntimeError(f"Erreur lors de la création du dossier : {str(e)}")

    # Uploads content to a blob.
    def put_file(self, destination_blob_name: str, content: bytes):
        """
        Uploads content to a blob.

        Args:
            destination_blob_name (str): Name of the destination blob.
            content (bytes): Content to upload.
        """
        try:
            destination_blob_name = destination_blob_name.replace("\\", "/")
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_string(content)
            print(f"📤 Fichier téléchargé vers {destination_blob_name}")
        except Exception as e:
            raise RuntimeError(f"Erreur lors de l'upload : {str(e)}")

    def get_file(self, source_blob_name: str) -> Optional[bytes]:
        """
        Downloads and returns the content of a blob.

        Args:
            source_blob_name (str): Blob path in the bucket.

        Returns:
            bytes: Content or None if not found.
        """
        try:
            source_blob_name = source_blob_name.replace("\\", "/")
            blob = self.bucket.blob(source_blob_name)
            if not blob.exists():
                return None

            buffer = io.BytesIO()
            blob.download_to_file(buffer)
            buffer.seek(0)
            return buffer.read()
        except GoogleAPIError as e:
            raise RuntimeError(f"Erreur lors de la lecture du fichier : {str(e)}")
        
    def delete_file(self, blob_name: str) -> bool:
        """
        Supprime un dossier (prefix) et tous ses fichiers dans le bucket GCS.

        Args:
            blob_name (str): Chemin du dossier ou du blob à supprimer dans le bucket.

        Returns:
            bool: True si au moins un fichier a été , False sinon.
        """
        try:
            blob_name = blob_name.replace("\\", "/")
            deleted = False
            # Supprime tous les blobs commençant par blob_name (dossier ou fichier)
            blobs = self.client.list_blobs(self.bucket_name, prefix=blob_name)
            for blob in blobs:
                blob.delete()
                # print(f"🗑️ Fichier supprimé : {blob.name}")
                deleted = True
            return deleted
        except Exception as e:
            print(f"Erreur lors de la suppression : {str(e)}")
            return False
        
    def list_files(self) -> List[str]:
        """
        Lists all files in the bucket.

        Returns:
            List[str]: Sorted list of file paths.
        """

        try:
            iterator = self.client.list_blobs(self.bucket_name)
            # get all folders inside local_folder
            prefixes = set()
            creation_time = {}
            for blob in iterator:
                parts = blob.name.split('/')
                if len(parts) > 2 and parts[0] == self.local_folder:
                    prefixes.add(parts[2])
                    creation_time[parts[2]] = blob.time_created
            #sort prefix list based on creation time list
            prefixes = sorted(prefixes, key=lambda p: creation_time[p])
            return (prefixes)
        except GoogleAPIError as e:
            raise RuntimeError(f"Erreur lors de la liste des projets : {str(e)}")

    def delete_all_projects(self):
        """
        Supprime tous les dossiers projets (sous-dossiers de self.local_folder) dans le bucket GCS.
        """
        try:
            # Liste tous les dossiers projets
            iterator = self.client.list_blobs(self.bucket_name, prefix=self.local_folder + "/")
            project_prefixes = set()
            for blob in iterator:
                parts = blob.name.split('/')
                if len(parts) > 1:
                    project_prefixes.add(parts[0] + "/" + parts[1])
            # Supprime chaque dossier projet
            for prefix in project_prefixes:
                self.delete_file(prefix)
            print(f"Tous les projets ont été supprimés dans GCS.")
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression de tous les projets : {str(e)}")
            return False
