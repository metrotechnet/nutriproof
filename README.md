# nutriss-parser

Application serveur pour le traitement automatisé de documents PDF (INAF).

## Description
Ce projet permet de téléverser un PDF, d’extraire et d’analyser les tableaux via des modèles d’IA afin de détecter et structurer les valeurs.

## Fonctionnalités principales
- Téléversement de documents PDF
- Extraction automatique des tableaux
- Traitement et structuration des données
- Interface web pour la gestion et la visualisation

## Installation
1. Cloner le dépôt :
    ```
    git clone https://github.com/dboulanger363/nutriss-parser.git
    cd nutriss-parser
    ```
2. Installer les dépendances Python :
    ```
    pip install -r requirements.txt
    ```

## Utilisation
1. Lancer le serveur Flask :
    ```
    python app.py
    ```
2. Accéder à l’interface web via : http://localhost:5000
3. Téléverser un PDF et consulter les résultats.

## Configuration
- Les fichiers de configuration se trouvent dans le dossier `py/`.
- Les fichiers statiques (CSS, JS, images) sont dans `static/`.
- Les templates HTML sont dans `templates/`.

## Support
Pour toute question : Denis Boulanger, dboulanger@cimmi.ca

## Contribution
Les contributions sont les bienvenues ! Veuillez ouvrir une issue ou soumettre une pull request.

## Auteur
Denis Boulanger, CIMMI (2025)

## Licence
Ce projet est sous licence MIT.

## Statut du projet
Projet en développement actif.

