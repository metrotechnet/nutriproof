# NutriProof — Mise à jour automatique

## Comment ça fonctionne

L'application utilise **electron-updater** + **GitHub Releases**.

Au lancement, l'app vérifie automatiquement s'il y a une nouvelle version sur GitHub. Si oui, elle la télécharge en arrière-plan, puis affiche un dialogue demandant à l'utilisateur de redémarrer.

---

---

## Publier une mise à jour

### Méthode 1 : CI/CD via GitHub Actions (recommandé)

1. Incrémenter la version dans `electron/package.json` :
   ```json
   "version": "1.1.0"
   ```

2. Commit, tag et push :
   ```bash
   git add -A
   git commit -m "v1.1.0"
   git tag v1.1.0
   git push origin main --tags
   ```

3. Le workflow GitHub Actions build automatiquement Windows + macOS et crée une GitHub Release avec les installeurs et les fichiers `latest.yml` / `latest-mac.yml`.

### Méthode 2 : Build local + publication

#### Prérequis

Créer un fichier `.env` à la racine du projet :
```
GH_TOKEN=ghp_votre_token_ici
```

Ou définir la variable d'environnement :
```powershell
$env:GH_TOKEN = "ghp_votre_token_ici"
```

#### Publier

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

### Vérifier sur GitHub

Aller sur `https://github.com/metrotechnet/nutriproof/releases` et confirmer que :
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
| `git tag v1.1.0 && git push origin v1.1.0` | Build CI/CD + publier (recommandé) |
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
