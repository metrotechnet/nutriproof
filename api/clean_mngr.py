import os
import shutil
from datetime import datetime, timedelta
import threading


class CleanManager:
    """
    Gère automatiquement le nettoyage de dossiers temporaires selon leur durée de vie.
    """

    def __init__(self, max_age_minutes=120, check_interval_seconds=300):
        """
        Initialise le gestionnaire de nettoyage.

        Args:
            max_age_minutes (int): Durée maximale avant suppression (en minutes)
            check_interval_seconds (int): Intervalle entre deux vérifications (en secondes)
        """
        self.folder_stack = []
        self.max_age = timedelta(minutes=max_age_minutes)
        self.check_interval = check_interval_seconds
        self._scheduler_thread = None

    def add_folder(self, folder_path):
        """
        Enregistre un dossier pour futur nettoyage.

        Args:
            folder_path (str): Chemin absolu du dossier
        """
        print(f"[CleanManager] Suivi ajouté : {folder_path}")
        self.folder_stack.append((folder_path, datetime.now()))

    def clear_folder(self, folder_path):
        """
        Vide le contenu d’un dossier (fichiers et sous-dossiers).

        Args:
            folder_path (str): Chemin du dossier à nettoyer
        """
        if not os.path.isdir(folder_path):
            print(f"[CleanManager] Inexistant ou non répertoire : {folder_path}")
            return

        for filename in os.listdir(folder_path):
            path = os.path.join(folder_path, filename)
            if filename.startswith('.'):
                continue  # Ignore fichiers cachés
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                print(f"[CleanManager] Supprimé : {path}")
            except Exception as e:
                print(f"[CleanManager] Erreur suppression {path} : {e}")

    def _delete_old_folders(self):
        now = datetime.now()
        remaining = []

        for folder_path, created_time in self.folder_stack:
            # Convertir en datetime si nécessaire
            if isinstance(created_time, str):
                created_time = datetime.fromisoformat(created_time)

            age = now - created_time
            if age > self.max_age:
                try:
                    if os.path.isdir(folder_path):
                        shutil.rmtree(folder_path)
                        print(f"[CleanManager] Dossier expiré supprimé : {folder_path}")
                except Exception as e:
                    print(f"[CleanManager] Erreur suppression {folder_path} : {e}")
            else:
                remaining.append((folder_path, created_time))

        self.folder_stack = remaining

    def _schedule_loop(self):
        self._delete_old_folders()
        threading.Timer(self.check_interval, self._schedule_loop).start()

    def start(self):
        """
        Démarre la boucle de nettoyage périodique.
        """
        print("[CleanManager] Démarrage de la surveillance des dossiers…")
        self._schedule_loop()
