# Signing checklist (production) + unsigned fallback

Le pipeline dans [build.yml](C:/dev/NUTRISS-OCR/.github/workflows/build.yml) supporte les deux modes:

- **Mode production signé** (recommandé pour diffusion utilisateurs)
- **Mode fallback unsigned** (si secrets/certificats absents)

Cette checklist corrige et centralise les secrets GitHub nécessaires pour que la signature fonctionne en production.

## 1) Secrets GitHub requis (production)

Configure ces secrets dans **GitHub > Settings > Secrets and variables > Actions > Repository secrets**.

### Windows (Azure Trusted Signing)

Actuellement, la signature Windows est désactivée dans [build.yml](C:/dev/NUTRISS-OCR/.github/workflows/build.yml) (étapes commentées).

Si vous réactivez la signature Windows, ces secrets deviennent requis:

- `ARTIFACT_SIGNING_ACCOUNT`
- `ARTIFACT_SIGNING_PROFILE`
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_SECRET`

### macOS signing (Developer ID Application)

Utilisés par `electron-builder`:

- `MAC_CSC_LINK` (certificat encodé/base64 ou lien vers le certificat)
- `MAC_CSC_KEY_PASSWORD` (mot de passe du certificat)
- `MAC_CSC_NAME` (nom exact de l’identité, ex: `Developer ID Application: ...`) — fortement recommandé

### macOS notarization (Apple)

Obligatoires pour l’étape `Notarize macOS app (Gatekeeper)` :

- `APPLE_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_TEAM_ID`

## 2) Comportement du pipeline si secrets manquants

- **Windows**: aucune signature n’est effectuée tant que les étapes restent commentées.
- **macOS build**: si les variables `MAC_CSC_*` sont absentes, le workflow construit un DMG **non signé** (`--config.mac.identity=null`).
- **macOS notarization**: si `APPLE_*` est absent, la notarization est ignorée.

## 3) Checklist de validation rapide

1. Vérifier que tous les secrets ci-dessus sont présents et sans espaces parasites.
2. Lancer un workflow sur un tag `v*`.
3. Contrôler les logs:
   - Windows: build `.exe` généré (non signé tant que les étapes de signature restent commentées).
   - macOS: build sans fallback unsigned, puis **Notarize macOS app** avec statut `Accepted`.
4. Vérifier les artefacts publiés:
   - `NutriProof-Setup.exe` (non signé si signature Windows désactivée)
   - `*.dmg` (notarisé + stapled)

## 4) Erreur fréquente

Erreur typique:

```text
SecKeychainUnlock: The user name or passphrase you entered is not correct.
```

Ce n’est pas un bug applicatif. C’est un problème de certificat/identité/keychain macOS côté CI ou de secret `MAC_CSC_*` incorrect.

## 5) Mode unsigned (usage interne uniquement)

Pour un build local non signé:

```bash
cd electron
npx electron-builder --mac --publish never --config.mac.identity=null
```

⚠️ Ce mode est pratique pour test interne, mais **pas adapté à une distribution production** (Gatekeeper affichera un avertissement ou bloquera l’ouverture).
