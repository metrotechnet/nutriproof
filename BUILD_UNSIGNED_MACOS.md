# Unsigned build configuration (GitHub Actions)

Le workflow [build.yml](C:/dev/NUTRISS-OCR/.github/workflows/build.yml) est actuellement configuré pour produire des builds **non signés**:

- Windows: build de l'installeur sans étape de signature
- macOS: build DMG avec `--config.mac.identity=null`
- notarization macOS: étape commentée (désactivée)

## 1) Secrets GitHub requis actuellement

### Windows (Azure Trusted Signing)

Actuellement, la signature Windows est désactivée dans [build.yml](C:/dev/NUTRISS-OCR/.github/workflows/build.yml) (étapes commentées).

Si vous réactivez la signature Windows, ces secrets deviennent requis:

- `ARTIFACT_SIGNING_ACCOUNT`
- `ARTIFACT_SIGNING_PROFILE`
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_SECRET`

### macOS signing (Developer ID Application)

Actuellement non utilisés car le build force le mode unsigned:

- `MAC_CSC_LINK` (certificat encodé/base64 ou lien vers le certificat)
- `MAC_CSC_KEY_PASSWORD` (mot de passe du certificat)
- `MAC_CSC_NAME` (nom exact de l’identité, ex: `Developer ID Application: ...`) — fortement recommandé

### macOS notarization (Apple)

Actuellement non utilisés car l’étape de notarization est commentée:

- `APPLE_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_TEAM_ID`

## 2) Comportement du pipeline si secrets manquants

- **Windows**: aucune signature n’est effectuée tant que les étapes restent commentées.
- **macOS build**: le workflow construit toujours un DMG **non signé** (`--config.mac.identity=null`).
- **macOS notarization**: aucune notarization n’est tentée tant que l’étape reste commentée.

## 3) Checklist de validation rapide

1. Vérifier qu’aucune étape de signature/notarization n’a été réactivée par erreur.
2. Lancer un workflow sur un tag `v*`.
3. Contrôler les logs:
   - Windows: build `.exe` généré.
   - macOS: build DMG avec `--config.mac.identity=null`.
4. Vérifier les artefacts publiés:
   - `NutriProof-Beta-Setup.exe` (non signé)
   - `*.dmg` (non signé / non notarisé)

## 4) Erreur fréquente

Erreur typique:

```text
SecKeychainUnlock: The user name or passphrase you entered is not correct.
```

Ce n’est pas un bug applicatif. C’est un problème de certificat/identité/keychain macOS côté CI.

## 5) Mode unsigned (usage interne uniquement)

Pour un build local non signé:

```bash
cd electron
npx electron-builder --mac --publish never --config.mac.identity=null
```

⚠️ Ce mode est pratique pour test interne, mais **pas adapté à une distribution production** (Gatekeeper affichera un avertissement ou bloquera l’ouverture).
