# NutriProof

Application desktop pour le traitement automatisé de documents PDF (INAF).

## Description
Ce projet permet de téléverser un PDF, d'extraire et d'analyser les tableaux via OCR (Tesseract) afin de détecter et structurer les valeurs.

## Fonctionnalités principales
- Téléversement de documents PDF
- Extraction automatique des tableaux (OCR local via Tesseract)
- Traitement et structuration des données
- Interface web intégrée dans une application Electron

## Prérequis

### Windows
- Python 3.10+ avec venv
- Node.js 18+ / npm
- Tesseract OCR 5.x installé dans `C:\Program Files\Tesseract-OCR`

### macOS
- Python 3.10+ avec venv
- Node.js 18+ / npm
- Homebrew : `brew install tesseract tesseract-lang`

## Installation (développement)
```bash
git clone https://github.com/dboulanger363/nutriproof.git
cd nutriproof
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cd electron && npm install && cd ..
```

## Lancer en mode développement
```bash
cd electron
npm start
```
Ceci lance le backend Flask (port 8080) + la fenêtre Electron.

---

## Build & Déploiement

### Windows — Build
```powershell
.\build-desktop.ps1
```
Options :
- `-SkipBackend` : ne rebuild que l'Electron (pas PyInstaller)
- `-SkipElectron` : ne rebuild que le backend Python
- `-TesseractSource "C:\chemin\vers\Tesseract-OCR"` : chemin Tesseract custom

**Résultat** : `dist\electron\NutriProof-win32-x64\NutriProof.exe`

### macOS — Build
```bash
chmod +x build-desktop-mac.sh
./build-desktop-mac.sh
```
Options :
- `--skip-backend` : ne rebuild que l'Electron
- `--skip-electron` : ne rebuild que le backend Python
- `--arch arm64` ou `--arch x64` : forcer l'architecture (auto-détecté par défaut)

**Résultat** : `dist/electron/NutriProof-darwin-arm64/NutriProof.app` (ou `-x64`)

---

## Déployer chez un utilisateur

### Première installation

1. **Builder** l'application sur la machine de dev (voir ci-dessus)
2. **Copier** le dossier complet de sortie vers la machine cible :
   - Windows : copier `dist\electron\NutriProof-win32-x64\` → clé USB ou partage réseau
   - macOS : copier `dist/electron/NutriProof-darwin-arm64/NutriProof.app` → DMG ou dossier
3. **Sur la machine cible** :
   - Windows : lancer `NutriProof.exe` directement (aucune installation requise, app portable)
   - macOS : glisser `NutriProof.app` dans `/Applications/`, puis lancer

> **Note** : Aucun runtime Python, Node.js ou Tesseract n'est requis sur la machine cible. Tout est embarqué dans le package.

### Mise à jour

Pour mettre à jour l'application chez un utilisateur :

1. **Sur la machine de dev** : faire les modifications au code, puis re-builder :
   ```powershell
   # Windows — rebuild complet
   .\build-desktop.ps1

   # Windows — seulement le backend (ex: changement Python)
   .\build-desktop.ps1 -SkipElectron

   # Windows — seulement l'Electron (ex: changement UI)
   .\build-desktop.ps1 -SkipBackend
   ```
   ```bash
   # macOS — rebuild complet
   ./build-desktop-mac.sh
   ```

2. **Remplacer** le dossier de l'application sur la machine cible :
   - Windows : supprimer l'ancien dossier `NutriProof-win32-x64\` et copier le nouveau
   - macOS : supprimer l'ancien `NutriProof.app` et copier le nouveau

3. Les **données utilisateur** (dossier `uploads/`) sont dans le dossier de l'application sous `resources/backend/uploads/`. Si on veut les préserver lors d'une mise à jour :
   - Sauvegarder le dossier `uploads/` avant la mise à jour
   - Le restaurer dans le nouveau package après copie

### Structure du package déployé

```
NutriProof-win32-x64/          # ou NutriProof-darwin-arm64/
├── NutriProof.exe              # ou NutriProof.app/
├── resources/
│   ├── backend/                # Backend Python (PyInstaller)
│   │   ├── app.exe             # ou app (macOS)
│   │   ├── templates/
│   │   ├── static/
│   │   ├── dbase/
│   │   └── uploads/main/       # Données utilisateur
│   └── tesseract-bundle/       # Tesseract OCR embarqué
└── ...
```

---

## Configuration
- `dbase/bilan_lipidique.json` : configuration des paramètres OCR à extraire
- `templates/` : templates HTML (index, review, maintenance)
- `static/` : fichiers CSS, JS, images

## Support
Pour toute question : Denis Boulanger, info@imxtech.ca

## Auteur
Denis Boulanger, IMX Technologie (2026)

## Licence
Ce projet est sous licence MIT.

## Statut du projet
Projet en développement actif.