# Azure Artifact Signing (Windows Installer)

This project can sign `NutriProof-Setup.exe` with Azure Artifact Signing (formerly Trusted Signing).

## Files added

- `azure-pipelines-artifact-signing.yml`: Azure DevOps build + sign pipeline template.
- `ci/artifact-signing/metadata.sample.json`: metadata template for SignTool `/dmdf`.
- `build-desktop.ps1`: optional local signing step.

## 1) Azure prerequisites

1. Create an Artifact Signing account in Azure.
2. Complete identity validation.
3. Create a certificate profile.
4. Grant your CI identity access to sign with that profile.

## 2) Build agent prerequisites

1. Windows SDK (SignTool, version 10.0.22621.755+).
2. .NET 8 runtime.
3. Azure Artifact Signing client tools (or manually provide `Azure.CodeSigning.Dlib.dll`).

Quick install on Windows (admin PowerShell):

```powershell
winget install -e --id Microsoft.Azure.ArtifactSigningClientTools
```

## 3) Metadata JSON

1. Copy `ci/artifact-signing/metadata.sample.json` to `metadata.json`.
2. Replace values:
   - `Endpoint`: region endpoint of your signing account.
   - `CodeSigningAccountName`: your account name.
   - `CertificateProfileName`: your certificate profile.
3. Keep `metadata.json` private (do not commit).

## 4) Local signing with build-desktop.ps1

Build and sign in one command:

```powershell
./build-desktop.ps1 -Installer -SignWithTrustedSigning -TrustedSigningDlibPath "C:\path\to\Azure.CodeSigning.Dlib.dll" -TrustedSigningMetadataPath "C:\path\to\metadata.json"
```

Alias also works:

```powershell
./build-desktop.ps1 -Installer -SignWithArtifactSigning -TrustedSigningDlibPath "C:\path\to\Azure.CodeSigning.Dlib.dll" -TrustedSigningMetadataPath "C:\path\to\metadata.json"
```

Optional timestamp override:

```powershell
./build-desktop.ps1 -Installer -SignWithArtifactSigning -TrustedSigningDlibPath "C:\path\to\Azure.CodeSigning.Dlib.dll" -TrustedSigningMetadataPath "C:\path\to\metadata.json" -TimestampUrl "http://timestamp.acs.microsoft.com/"
```

## 5) Azure DevOps pipeline setup

1. Create pipeline from `azure-pipelines-artifact-signing.yml`.
2. Add variable `azureServiceConnection` with your Azure RM service connection name.
3. Upload secure files in Azure DevOps Library:
   - `metadata.json`
   - `Azure.CodeSigning.Dlib.dll`
4. Run pipeline; output is published as artifact `signed-windows-installer`.

## Troubleshooting

- 403 during signing: endpoint region mismatch in `metadata.json`.
- `signtool.exe` not found: install/update Windows SDK.
- `SignerSign() failed`: usually endpoint/profile/auth mismatch.
- Signature invalid after a few days: ensure timestamping is enabled.
