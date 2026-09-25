# Éditeur de Configuration & Événements MIDI pour Ableton Live (.als)

Cette application de bureau autonome, développée en Python (via `CustomTkinter`), permet d'analyser, d'éditer et de gérer les **assignations de contrôleurs matériels** ainsi que les **événements de notes MIDI** (Pistes, Clips, Notes, Hauteur, Durée, Vélocité) directement dans les fichiers de projet Ableton Live (`.als`) sans altérer les sessions originales.

## Nouvelles Fonctionnalités v2.1

- 🎛️ **Prise en charge Native des Mappings Ableton Live** : Détecte l'ensemble des assignations physiques réelles (<kbd>Ctrl</kbd> + <kbd>M</kbd>) de Live 9, 10, 11 et 12 (via la structure native `<KeyMidi>`).
- 🏷️ **Identification des Contrôleurs Matériels (Hardware)** :
  - Ableton Live n'enregistrant que le canal MIDI et le CC/Note dans le fichier projet, l'application regroupe intelligemment les contrôles par Canal MIDI.
  - Vous pouvez nommer vos appareils physiques réels (ex: *Launch Control XL*, *Arturia KeyLab*, *Akai APC*, *Pédalier*) via le bouton **"🏷️ Nommer mes Contrôleurs..."**.
  - Chaque assignation affiche directement son badge matériel personnalisé.
  - Filtre dédié par matériel pour isoler les contrôles d'un périphérique spécifique.
- 🔍 **Recherche et Filtres Avancés** : Filtrez par matériel, par piste ou par type (CC / Note), ou recherchez en direct un nom de paramètre (*Cutoff*, *Send*, *Volume*).
- 🎹 **Extraction complète des Événements MIDI** : Pistes MIDI, clips (Session et Arrangement) et notes individuelles avec pitch (ex: C3), position temporelle, durée et vélocité.
- ⚡ **Actions Groupées (Batch)** : Décalage de canaux ou de numéros de CC pour les contrôleurs, transposition et vélocité pour les notes.
- 💾 **Export .als Non-Destructif** : Génère un nouveau fichier `.als` compressé en GZIP 100% compatible Ableton Live sans modifier le master d'origine.
- 📄 **Export JSON & Profils** : Sauvegarde des templates de mappings et des notes musicales en JSON.

## Prérequis

- Python 3.8 ou supérieur

## Installation & Lancement

1. Installez les dépendances nécessaires :
   ```bash
   pip install -r requirements.txt
   ```

2. Lancez l'application :
   ```bash
   python ableton_midi_editor.py
   ```

## Workflow d'Utilisation

1. **Chargement** : Cliquez sur *Importer Projet (.als)*.
2. **Identification Matérielle** :
   - Cliquez sur **🏷️ Nommer mes Contrôleurs...** pour donner le nom de vos appareils physiques à chaque canal MIDI détecté.
   - Les noms sont automatiquement mémorisés pour vos prochaines sessions.
3. **Visualisation & Filtrage** :
   - Filtrez par Matériel, par Piste ou via la barre de recherche.
4. **Édition** :
   - Modifiez le Canal, le CC, les bornes Min/Max et cliquez sur <kbd>✓</kbd>.
5. **Exportation** :
   - Cliquez sur *Régénérer et Exporter* pour créer un **nouveau** fichier `.als`.
