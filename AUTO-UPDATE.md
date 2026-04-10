# NutriProof — Mise à jour automatique

## Comment ça fonctionne

L'application utilise **electron-updater** + **GitHub Releases**.

Au lancement, l'app vérifie automatiquement s'il y a une nouvelle version sur GitHub. Si oui, elle la télécharge en arrière-plan, puis affiche un dialogue demandant à l'utilisateur de redémarrer.

---

## Prérequis (une seule fois)

### 1. Créer un GitHub Personal Access Token

1. Aller sur GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Cliquer **Generate new token (classic)**
3. Sélectionner le scope **`repo`** (accès complet aux repositories)
4. Copier le token généré

### 2. Configurer la variable d'environnement

Avant de publier, définir le token dans votre terminal :

```powershell
# Windows (session courante)
$env:GH_TOKEN = "ghp_votre_token_ici"

# Windows (permanent, PowerShell en tant qu'admin)
[Environment]::SetEnvironmentVariable("GH_TOKEN", "ghp_votre_token_ici", "User")
```

```bash
# macOS / Linux
export GH_TOKEN="ghp_votre_token_ici"

# Permanent (ajouter dans ~/.zshrc ou ~/.bashrc)
echo 'export GH_TOKEN="ghp_votre_token_ici"' >> ~/.zshrc
```

---

## Publier une mise à jour

### Étape 1 : Incrémenter la version

Modifier la version dans `electron/package.json` :

```json
"version": "1.1.0"
```

Utiliser le format **semver** :
- `1.0.1` — correctif (bug fix)
- `1.1.0` — nouvelle fonctionnalité
- `2.0.0` — changement majeur

### Étape 2 : Builder et publier

```powershell
# Windows — build complet + installeur + publication GitHub
.\build-desktop.ps1 -Installer -Publish

# Windows — installeur seulement (test local, sans publier)
.\build-desktop.ps1 -Installer
```

```bash
# macOS — build complet + installeur + publication GitHub
./build-desktop-mac.sh --installer --publish
```

Cela va :
1. Compiler le backend Python avec PyInstaller
2. Bundler Tesseract OCR
3. Créer l'installeur NSIS (`.exe`) ou DMG (`.dmg`)
4. Créer automatiquement une **GitHub Release** avec :
   - Le fichier installeur
   - Le fichier `latest.yml` (ou `latest-mac.yml`) nécessaire à l'auto-update

### Étape 3 : Vérifier sur GitHub

Aller sur `https://github.com/dboulanger363/nutriproof/releases` et confirmer que :
- La release correspond à la bonne version
- Les fichiers `.exe` et `latest.yml` sont présents

---

## Ce que voit l'utilisateur

1. L'app vérifie les mises à jour **5 secondes après le lancement**
2. Si une mise à jour existe, elle se **télécharge silencieusement** en arrière-plan
3. Une fois le téléchargement terminé, un dialogue apparaît :

   > **Mise à jour disponible**
   >
   > La version X.Y.Z a été téléchargée.
   > L'application va redémarrer pour appliquer la mise à jour.
   >
   > [Redémarrer maintenant] [Plus tard]

4. Si l'utilisateur choisit **Plus tard**, la mise à jour sera appliquée au prochain lancement de l'app

---

## Commandes de build

| Commande | Description |
|---|---|
| `.\build-desktop.ps1` | Build portable (dossier, pas d'auto-update) |
| `.\build-desktop.ps1 -Installer` | Build installeur NSIS (auto-update, local) |
| `.\build-desktop.ps1 -Installer -Publish` | Build + publier sur GitHub Releases |
| `.\build-desktop.ps1 -SkipBackend -Installer` | Rebuild installeur sans recompiler Python |
| `.\build-desktop.ps1 -SkipElectron` | Recompiler seulement le backend Python |

---

## Notes importantes

- **L'auto-update ne fonctionne qu'avec le build `-Installer`** (NSIS), pas le build portable (dossier)
- Le repo GitHub doit être **public**, ou le token du client doit avoir accès au repo privé
- La **première installation** chez un client est toujours manuelle (copie de l'installeur)
- Les mises à jour suivantes sont automatiques
- L'utilisateur a toujours le choix de reporter la mise à jour
- Les **données utilisateur** dans `uploads/` sont préservées lors des mises à jour automatiques (contrairement au mode portable)

---

## Dépannage

| Problème | Cause | Solution |
|---|---|---|
| `Error: GH_TOKEN is not set` | Token GitHub manquant | Définir `$env:GH_TOKEN` avant de publier |
| `Error: 404 Not Found` | Repo GitHub introuvable | Vérifier `owner` et `repo` dans `package.json` → `build.publish` |
| L'app ne détecte pas la mise à jour | Version non incrémentée | Vérifier que `package.json` a une version plus récente |
| L'app ne détecte pas la mise à jour | Fichier `latest.yml` manquant | Vérifier la release GitHub, re-publier si nécessaire |
| L'update ne se télécharge pas | Pas de connexion Internet | L'app réessaiera au prochain lancement |
