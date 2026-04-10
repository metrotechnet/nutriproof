# NutriProof — Guide d'installation

## Windows

### Installation

1. Vous recevrez un dossier nommé **`NutriProof-win32-x64`** (par clé USB, partage réseau ou lien de téléchargement).

2. **Copier** le dossier complet à l'emplacement de votre choix, par exemple :
   - `C:\NutriProof\`
   - `C:\Users\VotreNom\Desktop\NutriProof\`
   - Ou tout autre dossier où vous avez les droits d'écriture.

3. **Lancer l'application** en double-cliquant sur :
   ```
   NutriProof-win32-x64\NutriProof.exe
   ```

4. *(Facultatif)* Pour un accès rapide, faites un clic droit sur `NutriProof.exe` → **Créer un raccourci**, puis déplacez le raccourci sur votre Bureau.

> **Aucune installation supplémentaire n'est requise.** Tout est inclus dans le dossier (Python, Tesseract OCR, etc.).

### Premier lancement

- Au premier lancement, Windows peut afficher un avertissement **« Windows a protégé votre ordinateur »**.
- Cliquer sur **« Informations complémentaires »** puis **« Exécuter quand même »**.
- Cet avertissement n'apparaîtra qu'une seule fois.

---

## macOS

### Installation

1. Vous recevrez un fichier **`NutriProof.app`** (ou un dossier contenant l'application).

2. **Glisser** `NutriProof.app` dans le dossier **Applications** :
   - Ouvrir le Finder
   - Glisser `NutriProof.app` dans `/Applications/`

3. **Lancer l'application** depuis le Launchpad ou le dossier Applications.

### Premier lancement

- macOS peut afficher un message **« NutriProof ne peut pas être ouvert car le développeur ne peut pas être vérifié »**.
- Pour autoriser l'ouverture :
  1. Aller dans **Préférences Système** → **Confidentialité et sécurité**
  2. Dans la section « Sécurité », cliquer sur **« Ouvrir quand même »**
- Ou bien : faire un **clic droit** (Ctrl+clic) sur l'application → **Ouvrir** → **Ouvrir**.

---

## Utilisation

1. L'application s'ouvre avec la page de **gestion des fichiers**.
2. **Téléverser un PDF** en cliquant sur le bouton d'upload.
3. Lancer le **traitement OCR** pour extraire les données du document.
4. **Réviser les résultats** dans la page de révision.
5. **Exporter en Excel** les données extraites.

---

## Vos données

- Vos fichiers (PDF uploadés, résultats OCR) sont stockés **localement** dans le dossier de l'application.
- Aucune donnée n'est envoyée sur Internet.
- Emplacement des données :
  - Windows : `NutriProof-win32-x64\resources\backend\uploads\`
  - macOS : `NutriProof.app/Contents/Resources/backend/uploads/`

---

## Mise à jour

Quand une nouvelle version vous est fournie :

1. **Sauvegarder vos données** (si vous souhaitez les conserver) :
   - Copier le dossier `uploads` depuis l'emplacement ci-dessus vers un endroit temporaire.

2. **Supprimer** l'ancien dossier `NutriProof-win32-x64` (ou l'ancienne `NutriProof.app`).

3. **Copier** le nouveau dossier/application au même emplacement.

4. **Restaurer vos données** :
   - Recopier le dossier `uploads` sauvegardé à l'étape 1 dans le nouveau dossier de l'application.

---

## Dépannage

| Problème | Solution |
|---|---|
| L'application ne se lance pas | Vérifier que le dossier est complet (ne pas supprimer de fichiers à l'intérieur) |
| Message « Windows a protégé votre ordinateur » | Cliquer « Informations complémentaires » → « Exécuter quand même » |
| Message « développeur non vérifié » (macOS) | Clic droit → Ouvrir, ou autoriser dans Préférences Système |
| L'OCR ne détecte rien | Vérifier que le PDF contient des pages scannées lisibles |
| Écran blanc au démarrage | Patienter quelques secondes, le serveur interne démarre |

---

## Support

Pour toute question ou problème : **Denis Boulanger** — info@imxtech.ca
