import gzip
import xml.etree.ElementTree as ET
import json

class AbletonMidiEditor:
    def __init__(self):
        self.file_path = None
        self.tree = None
        self.root = None
        
    def load_project(self, file_path):
        """Charge le projet Ableton (.als) compressé en GZIP et parse le XML."""
        self.file_path = file_path
        with gzip.open(self.file_path, 'rb') as f:
            xml_data = f.read()
        self.root = ET.fromstring(xml_data)
        self.tree = ET.ElementTree(self.root)
        
    def get_mappings(self):
        """Récupère tous les mappings MIDI existants dans le projet."""
        mappings = []
        if self.root is None:
            return mappings
            
        for mapping in self.root.iter('MidiMappingRange'):
            id_elem = mapping.find('Id')
            channel_elem = mapping.find('MidiControllerChannel')
            cc_elem = mapping.find('MidiControllerNumber')
            
            target_elem = mapping.find('RangeTarget')
            lockable_param = target_elem.find('LockableParameter') if target_elem is not None else None
            
            min_elem = target_elem.find('Min') if target_elem is not None else None
            max_elem = target_elem.find('Max') if target_elem is not None else None
            
            if id_elem is not None and channel_elem is not None and cc_elem is not None:
                target_id = lockable_param.get('Id') if lockable_param is not None else "Unknown"
                mappings.append({
                    'id': id_elem.get('Value'),
                    'channel': channel_elem.get('Value'),
                    'cc': cc_elem.get('Value'),
                    'target_id': target_id,
                    'min': min_elem.get('Value') if min_elem is not None else "N/A",
                    'max': max_elem.get('Value') if max_elem is not None else "N/A"
                })
        return mappings

    def update_mapping(self, mapping_id, new_channel, new_cc, new_min=None, new_max=None):
        """Met à jour un mapping spécifique (Canal, CC, Min, Max) dans l'arbre XML."""
        if self.root is None:
            return False
            
        for mapping in self.root.iter('MidiMappingRange'):
            id_elem = mapping.find('Id')
            if id_elem is not None and id_elem.get('Value') == str(mapping_id):
                channel_elem = mapping.find('MidiControllerChannel')
                cc_elem = mapping.find('MidiControllerNumber')
                
                if channel_elem is not None:
                    channel_elem.set('Value', str(new_channel))
                if cc_elem is not None:
                    cc_elem.set('Value', str(new_cc))
                    
                target_elem = mapping.find('RangeTarget')
                if target_elem is not None:
                    if new_min is not None and new_min != "N/A":
                        min_elem = target_elem.find('Min')
                        if min_elem is not None:
                            min_elem.set('Value', str(new_min))
                    if new_max is not None and new_max != "N/A":
                        max_elem = target_elem.find('Max')
                        if max_elem is not None:
                            max_elem.set('Value', str(new_max))
                return True
        return False

    def export_project(self, output_path):
        """Regénère le fichier .als en compressant l'arbre XML modifié."""
        if self.root is None:
            return
        # Ableton utilise l'encodage utf-8 pour son XML interne
        xml_str = ET.tostring(self.root, encoding='utf-8', xml_declaration=True)
        with gzip.open(output_path, 'wb') as f:
            f.write(xml_str)
            
    def save_template(self, output_path):
        """Sauvegarde les mappings actuels sous forme de fichier profil (JSON)."""
        mappings = self.get_mappings()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mappings, f, indent=4)
            
    def load_template(self, template_path):
        """Applique un fichier profil (JSON) en liant les LockableParameter Id."""
        with open(template_path, 'r', encoding='utf-8') as f:
            template_mappings = json.load(f)
            
        # Création d'un dictionnaire de recherche rapide par 'target_id'
        template_lookup = {
            m.get('target_id'): m 
            for m in template_mappings 
            if m.get('target_id') and m.get('target_id') != "Unknown"
        }
            
        for current_mapping in self.root.iter('MidiMappingRange'):
            target_elem = current_mapping.find('RangeTarget')
            lockable_param = target_elem.find('LockableParameter') if target_elem is not None else None
            
            if lockable_param is not None:
                target_id = lockable_param.get('Id')
                if target_id in template_lookup:
                    new_mapping = template_lookup[target_id]
                    cc_elem = current_mapping.find('MidiControllerNumber')
                    channel_elem = current_mapping.find('MidiControllerChannel')
                    
                    if cc_elem is not None and 'cc' in new_mapping:
                        cc_elem.set('Value', str(new_mapping['cc']))
                    if channel_elem is not None and 'channel' in new_mapping:
                        channel_elem.set('Value', str(new_mapping['channel']))
                        
                    if 'min' in new_mapping and new_mapping['min'] != "N/A":
                        min_elem = target_elem.find('Min')
                        if min_elem is not None:
                            min_elem.set('Value', str(new_mapping['min']))
                            
                    if 'max' in new_mapping and new_mapping['max'] != "N/A":
                        max_elem = target_elem.find('Max')
                        if max_elem is not None:
                            max_elem.set('Value', str(new_mapping['max']))
