# macOS signing and notarization

Le workflow GitHub Actions [build.yml](.github/workflows/build.yml) est configuré pour tenter un build macOS signé et notarisé lorsque les secrets Apple sont fournis.

## 1) Secrets GitHub requis

### macOS signing (Developer ID Application)

Ces secrets doivent être ajoutés dans les repository or organization secrets:

- `MAC_CSC_LINK` (ou `CSC_LINK`), le certificat encodé/base64 ou le chemin vers le .p12
- `MAC_CSC_KEY_PASSWORD` (ou `CSC_KEY_PASSWORD`)
- `MAC_CSC_NAME` (ou `CSC_NAME`), par exemple `Developer ID Application: Acme Inc. (TEAMID)`

### macOS notarization (Apple)

- `APPLE_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_TEAM_ID`

## 2) Comportement du pipeline

- Le build macOS appelle `electron-builder` sans `--config.mac.identity=null`.
- Le hook `electron/signing/afterSign.js` resigne aussi les binaires mach-O internes pour éviter les échecs de notarization.
- La step de notarization est exécutée uniquement si les secrets Apple sont présents.
- Si un secret manque, le pipeline affiche un message explicite et continue avec un build non signé localement; ce comportement est utile pour les tests, mais il ne doit pas être utilisé pour une distribution publique.

## 3) Checklist de validation rapide

1. Vérifier que les secrets Apple sont bien présents dans GitHub.
2. Lancer un workflow sur un tag `v*`.
3. Contrôler les logs du job `build-macos`:
   - signature des binaires .app
   - génération du DMG
   - étape de notarization si les secrets sont configurés
4. Vérifier les artefacts publiés:
   - `*.dmg`
   - `latest-mac.yml`

## 4) Erreur fréquente

```text
SecKeychainUnlock: The user name or passphrase you entered is not correct.
```

Ce n’est pas un bug applicatif. Il s’agit d’un problème de certificat, d’identité ou de keychain macOS côté CI.

## 5) Build local sans signature

Pour un build local non signé uniquement, par exemple en test rapide:

```bash
cd electron
npx electron-builder --mac --publish never --config.mac.identity=null
```

⚠️ Ce mode est pratique pour un test interne, mais il n’est pas adapté à une distribution publique car Gatekeeper peut afficher un avertissement ou bloquer l’ouverture de l’application.
