# NutriProof — Guide d'installation

## Téléchargement

Rendez-vous sur **https://imx-nutriproof.web.app** ou téléchargez directement :
- **Windows** : [NutriProof-Setup.exe](https://github.com/metrotechnet/nutriproof/releases/latest/download/NutriProof-Setup.exe)
- **macOS** : [NutriProof.dmg](https://github.com/metrotechnet/nutriproof/releases/latest/download/NutriProof.dmg)

## Windows

### Installation

1. Téléchargez **NutriProof-Setup.exe** depuis le lien ci-dessus.

2. **Lancez l'installeur** en double-cliquant dessus.

3. Suivez les étapes d'installation (vous pouvez choisir le dossier d'installation).

4. L'application est accessible depuis le **Menu Démarrer** et un raccourci est créé sur le **Bureau**.

> **Aucune installation supplémentaire n'est requise.** Tout est inclus (Python, Tesseract OCR, etc.).

### Premier lancement

- Au premier lancement, Windows peut afficher un avertissement **« Windows a protégé votre ordinateur »**.
- Cliquer sur **« Informations complémentaires »** puis **« Exécuter quand même »**.
- Cet avertissement n'apparaîtra qu'une seule fois.

---

## macOS

### Installation

1. Téléchargez **NutriProof.dmg** depuis le lien ci-dessus.

2. **Ouvrez** le fichier `.dmg` et **glissez** `NutriProof.app` dans le dossier **Applications**.

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

L'application vérifie automatiquement les mises à jour au lancement. Si une nouvelle version est disponible :
1. Elle se télécharge en arrière-plan
2. Un dialogue vous propose de redémarrer pour appliquer la mise à jour
3. Vos données sont préservées automatiquement

> Il n'est plus nécessaire de remplacer manuellement les fichiers.

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
