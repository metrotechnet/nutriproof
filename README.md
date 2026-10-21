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
git clone https://github.com/metrotechnet/nutriproof.git
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

## Téléchargement

Les installeurs sont disponibles sur le site web : **https://imx-nutriproof.web.app**

Ou directement, en fonction de la version publiée :
- **Windows** : [NutriProof_v${version}-Setup.exe](https://github.com/metrotechnet/nutriproof/releases/download/v1.1.82/NutriProof_v1.1.82-Setup.exe)
- **macOS** : [NutriProof_v${version}.dmg](https://github.com/metrotechnet/nutriproof/releases/download/v1.1.82/NutriProof_v1.1.82.dmg)

Remplacez `v1.1.82` par la version exacte publiée dans GitHub Releases si vous souhaitez télécharger une version différente.

L'application inclut les mises à jour automatiques via electron-updater.

---

## Build & Déploiement

### CI/CD — GitHub Actions (recommandé)

Le workflow `.github/workflows/build.yml` build automatiquement Windows + macOS :

```bash
# Incrémenter la version dans electron/package.json, puis :
git tag v1.0.1
git push origin v1.0.1
```

Cela déclenche :
1. Build Windows (`NutriProof-Setup.exe`)
2. Build macOS (`NutriProof.dmg`)
3. Création d'une GitHub Release avec les deux installeurs

Pour lancer un build sans release :
- Aller sur GitHub → Actions → "Build & Release" → "Run workflow"

### Build local — Windows
```powershell
.\build-desktop.ps1
```
Options :
- `-Installer` : créer un installeur NSIS (avec auto-update)
- `-Installer -Publish` : créer + publier sur GitHub Releases
- `-SkipBackend` : ne rebuild que l'Electron
- `-SkipElectron` : ne rebuild que le backend Python

### Build local — macOS
```bash
chmod +x build-desktop-mac.sh
./build-desktop-mac.sh
```
Options : `--skip-backend`, `--skip-electron`, `--arch arm64|x64`

### Créer un ZIP macOS (run local, sans signature)

Pour distribuer une version web locale (Python + navigateur) avec un lanceur `start.command`:

```bash
chmod +x build-mac-local-zip.sh
./build-mac-local-zip.sh
```

Depuis Windows (PowerShell natif) :

```powershell
.\build-mac-local-zip.ps1
```

Sortie:
- `dist/NutriProof-mac-local.zip`
- Contient `start.command` que l'utilisateur macOS peut double-cliquer pour démarrer le serveur.

---

## Déployer le site web

```bash
cd website
firebase deploy --only hosting
```
Ou double-cliquer sur `deploy-website.bat`.

Site : https://imx-nutriproof.web.app

---

## Déployer sur GCP (projet `nutriproof-imx`)

Important :
- Le frontend **de l'application** est servi par Flask depuis [templates/](./templates) et [static/](./static).
- Donc ce frontend est inclus automatiquement dans l'image API et déployé via Cloud Run.
- Le dossier [website/public](./website/public) correspond au site statique (landing/téléchargement), déployé via Firebase Hosting.

Scripts PowerShell fournis :

- Build image API : [scripts/build-gcp-api.ps1](./scripts/build-gcp-api.ps1)
- Deploy API (Cloud Run) : [scripts/deploy-gcp-api.ps1](./scripts/deploy-gcp-api.ps1)
- App principale Firebase (nutriproof-imx.web.app) : [scripts/deploy-hosting-app.ps1](./scripts/deploy-hosting-app.ps1)
- Site statique website/public (Firebase Hosting) : [scripts/deploy-website-static.ps1](./scripts/deploy-website-static.ps1)

### 1) Builder/pusher l'image API

```powershell
.\scripts\build-gcp-api.ps1 -ProjectId nutriproof-imx -ImageTag latest
```

Options utiles :
- `-Region` (défaut : `northamerica-northeast1`)
- `-ServiceName` (défaut : `nutriproof-api`)
- `-ImageTag` (défaut : `latest`)

### 2) Déployer l'API sur Cloud Run

```powershell
.\scripts\deploy-gcp-api.ps1 -ProjectId nutriproof-imx -ImageTag latest -StorageMode gcs -GcsBucket nutriproof-imx-uploads -AllowUnauthenticated
```

Option alternative pour forcer une image précise :

```powershell
.\scripts\deploy-gcp-api.ps1 -ProjectId nutriproof-imx -ImageUri "northamerica-northeast1-docker.pkg.dev/nutriproof-imx/nutriproof/nutriproof-api:latest" -StorageMode gcs -GcsBucket nutriproof-imx-uploads -AllowUnauthenticated
```

Pour revenir au comportement local (build Mac/desktop), utiliser :

```powershell
.\scripts\deploy-gcp-api.ps1 -ProjectId nutriproof-imx -ImageTag latest -StorageMode local -AllowUnauthenticated
```

### 3) Déployer sur une VM GCP avec disque persistant

Cette option conserve les fichiers de travail sur un disque SSD persistant, sans dépendre du bucket Cloud Storage comme stockage principal.

```powershell
.\scripts\deploy-gcp-vm-with-disk.ps1 `
  -ProjectId nutriproof-imx `
  -Region northamerica-northeast1 `
  -Zone northamerica-northeast1-a `
  -InstanceName nutriproof-vm `
  -DiskName nutriproof-data `
  -DiskSizeGb 200 `
  -MachineType e2-standard-2 `
  -AppPort 8080 `
  -DomainName imxtech.ca `
  -Subdomain nutriproof
```

Le script :
- crée ou réutilise une VM Ubuntu
- crée un disque SSD persistant et le monte à `/mnt/nutriproof`
- installe Docker + Docker Compose
- crée un IP statique et l’attache à la VM
- clone le dépôt dans `/opt/nutriproof`
- configure `UPLOAD_ROOT=/mnt/nutriproof/uploads`
- crée un service `systemd` pour relancer l’application après un reboot du VM
- met à jour automatiquement l’enregistrement DNS A `nutriproof.imxtech.ca` si une zone Cloud DNS est trouvée
- lance l'application avec `docker compose up -d --build`

### 4) Déployer l'app principale vers nutriproof-imx.web.app (hosting:app)

```powershell
.\scripts\deploy-hosting-app.ps1 -ProjectId nutriproof-imx
```

### 5) Déployer le site statique website/public vers imx-nutriproof.web.app (hosting:website)

```powershell
.\scripts\deploy-website-static.ps1 -ProjectId imx-nutriproof
```

Prérequis CLI :
- `gcloud auth login` + `gcloud auth application-default login`
- `firebase login`

---

## Configuration
- `dbase/parameters.json` : configuration des types de formulaires et paramètres OCR à extraire
- `templates/` : templates HTML (index, review, maintenance)
- `static/` : fichiers CSS, JS, images

## Support
Pour toute question : Denis Boulanger — info@imxtech.ca

## Auteur
Denis Boulanger — [IMX Technologie](https://imx-nutriproof.web.app) (2026)

## Licence
Ce projet est sous licence MIT.

## Statut du projet
Projet en développement actif.