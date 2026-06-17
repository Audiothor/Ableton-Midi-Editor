# Éditeur de Configuration MIDI pour Ableton Live (.als)

Cette application de bureau autonome, développée en Python (via `CustomTkinter`), permet d'éditer, analyser et d'appliquer des templates de contrôleurs MIDI directement sur les fichiers de projet Ableton Live (`.als`) sans altérer les sessions originales.

## Prérequis

- Python 3.8 ou supérieur

## Installation & Lancement

1. Installez les dépendances nécessaires (le framework UI) :
   ```bash
   pip install -r requirements.txt
   ```

2. Lancez l'application :
   ```bash
   python app.py
   ```

## Workflow d'Utilisation

1. **Chargement** : Cliquez sur *Importer Projet (.als)* pour charger votre projet en lecture seule.
2. **Analyse & Visualisation** : La grille s'actualise avec la liste des mappings existants (Canal, Note/CC, Paramètre Cible).
3. **Édition** :
   - Modifiez manuellement le Canal ou le CC, et cliquez sur *Appliquer*.
   - Ou cliquez sur *Appliquer Template* pour charger un profil `.json` existant (qui mappera automatiquement les `LockableParameter Id` correspondants).
4. **Exportation** : Cliquez sur *Régénérer et Exporter* pour créer un **nouveau** fichier `.als`. Le fichier source ne sera jamais écrasé.

## Création d'un Exécutable Autonome (Standalone)

Pour distribuer cette application sous forme de fichier exécutable sans nécessiter l'installation de Python chez l'utilisateur final :

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --windowed app.py
```

L'exécutable généré se trouvera dans le dossier `dist/`.
