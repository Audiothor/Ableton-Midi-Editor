import gzip
import xml.etree.ElementTree as ET
import json
import os
import glob
import re
import ctypes
from ctypes import wintypes

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_MAP = {
    "C": 0, "C#": 1, "DB": 1,
    "D": 2, "D#": 3, "EB": 3,
    "E": 4,
    "F": 5, "F#": 6, "GB": 6,
    "G": 7, "G#": 8, "AB": 8,
    "A": 9, "A#": 10, "BB": 10,
    "B": 11
}

CONFIG_HARDWARE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hardware_profiles.json")

def midi_pitch_to_name(pitch):
    """Convertit un numéro de note MIDI (0-127) en nom de note (ex: 60 -> C3)."""
    try:
        p = int(pitch)
        if 0 <= p <= 127:
            octave = (p // 12) - 2
            return f"{NOTE_NAMES[p % 12]}{octave}"
    except (ValueError, TypeError):
        pass
    return str(pitch)

def note_name_to_pitch(val):
    """Convertit un nom de note (ex: C3, D#4, Eb2) ou un entier en numéro MIDI (0-127)."""
    if val is None:
        return None
    val_str = str(val).strip().upper()
    try:
        p = int(val_str)
        if 0 <= p <= 127:
            return p
    except ValueError:
        pass
        
    if len(val_str) >= 2:
        if len(val_str) >= 3 and val_str[1] in ('#', 'B'):
            n_part = val_str[:2]
            oct_part = val_str[2:]
        else:
            n_part = val_str[:1]
            oct_part = val_str[1:]
        try:
            octave = int(oct_part)
            if n_part in NOTE_MAP:
                pitch = (octave + 2) * 12 + NOTE_MAP[n_part]
                if 0 <= pitch <= 127:
                    return pitch
        except ValueError:
            pass
    return None


class AbletonMidiEditor:
    def __init__(self):
        self.file_path = None
        self.tree = None
        self.root = None
        self.creator = "Inconnu"
        self.param_lookup = {}
        self.hardware_aliases = self.load_hardware_aliases()
        self._mappings_cache = []
        
    # ==================== CONFIGURATION DES ALIAS HARDWARE ====================
    def load_hardware_aliases(self):
        """Charge les noms de contrôleurs matériels enregistrés par l'utilisateur."""
        if os.path.exists(CONFIG_HARDWARE_FILE):
            try:
                with open(CONFIG_HARDWARE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_hardware_aliases(self, aliases=None):
        """Sauvegarde les noms de contrôleurs matériels dans le fichier local."""
        if aliases is not None:
            self.hardware_aliases.update(aliases)
        try:
            with open(CONFIG_HARDWARE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.hardware_aliases, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def set_hardware_alias(self, channel, alias_name):
        """Définit un alias matériel pour un canal MIDI donné."""
        self.hardware_aliases[str(channel)] = str(alias_name).strip()
        self.save_hardware_aliases()
        for m in self._mappings_cache:
            if m.get('channel') == str(channel):
                m['hardware_name'] = str(alias_name).strip()

    def detect_available_hardware(self):
        """Détecte automatiquement les matériels et surfaces de contrôle configurés dans Ableton Live et Windows."""
        all_devs = set()
        all_surfaces = set()
        
        # 1. Scanner les fichiers de logs Ableton Live
        log_patterns = [
            os.path.expandvars(r'%APPDATA%\Ableton\Live *\Preferences\Log.txt'),
            os.path.expandvars(r'%USERPROFILE%\AppData\Roaming\Ableton\Live *\Preferences\Log.txt')
        ]
        logs = []
        for pat in log_patterns:
            logs.extend(glob.glob(pat))
        logs = sorted(list(set(logs)), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
        
        for log_path in logs:
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                devs = set(re.findall(r'MidiInDevice \[Name="([^"]+)"', content))
                surfaces = set(re.findall(r'Control Surface="([^"]+)"', content)) - {'None'}
                
                for d in devs:
                    if d not in ['Computer Keyboard', 'Microsoft GS Wavetable Synth']:
                        base = re.sub(r'\s*\(Port\s*\d+\)', '', d).strip()
                        if base:
                            all_devs.add(base)
                            
                for s in surfaces:
                    s_clean = s.replace('_', ' ').strip()
                    if s_clean and s_clean != 'AbletonMCP':
                        all_surfaces.add(s_clean)
            except Exception:
                pass
                
        # 2. Scanner les périphériques Windows connectés en direct via winmm.dll
        try:
            winmm = ctypes.windll.winmm
            class MIDIINCAPSW(ctypes.Structure):
                _fields_ = [
                    ('wMid', wintypes.WORD),
                    ('wPid', wintypes.WORD),
                    ('vDriverVersion', wintypes.DWORD),
                    ('szPname', wintypes.WCHAR * 32),
                    ('dwSupport', wintypes.DWORD)
                ]
            num_devs = winmm.midiInGetNumDevs()
            for i in range(num_devs):
                caps = MIDIINCAPSW()
                if winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                    name = caps.szPname.strip()
                    if name:
                        all_devs.add(name)
        except Exception:
            pass
            
        all_unique = sorted(list(set(list(all_surfaces) + list(all_devs))))
        return {
            'devices': sorted(list(all_devs)),
            'surfaces': sorted(list(all_surfaces)),
            'all_names': all_unique
        }

    def get_channel_groups(self):
        """Regroupe les mappings par canal MIDI avec analyse d'usage et suggestions matérielles."""
        mappings = self.get_mappings()
        groups = {}
        for m in mappings:
            ch = m['channel']
            if ch not in groups:
                groups[ch] = {
                    'channel': ch,
                    'count': 0,
                    'ccs': set(),
                    'params': [],
                    'name': self.hardware_aliases.get(ch, f"Contrôleur Ch. {ch}")
                }
            groups[ch]['count'] += 1
            try:
                groups[ch]['ccs'].add(int(m['cc']))
            except ValueError:
                pass
            p_desc = f"{m.get('track', '')} ({m.get('param', '')})"
            if len(groups[ch]['params']) < 3 and p_desc not in groups[ch]['params']:
                groups[ch]['params'].append(p_desc)
                
        hw_info = self.detect_available_hardware()
        all_hw = hw_info['all_names']
        
        result = []
        for ch in sorted(groups.keys(), key=lambda x: int(x) if x.isdigit() else 99):
            g = groups[ch]
            g['ccs_summary'] = sorted(list(g['ccs']))
            
            # Suggestion automatique basée sur l'analyse musicale des paramètres
            params_str = " ".join(g['params']).lower()
            suggested = None
            if any(k in params_str for k in ['send', 'volume', 'pan', 'mix']):
                for h in all_hw:
                    if any(k in h.lower() for k in ['control', 'twister', 'mixer', 'apc', 'nano']):
                        suggested = h
                        break
            elif any(k in params_str for k in ['cutoff', 'filter', 'synth', 'flt', 'drive', 'lead']):
                for h in all_hw:
                    if any(k in h.lower() for k in ['oxygen', 'key', 'pro 25', 'keyboard']):
                        suggested = h
                        break
            elif any(k in params_str for k in ['track', 'mute', 'pad', 'solo', 'arm']):
                for h in all_hw:
                    if any(k in h.lower() for k in ['launchpad', 'pad', 'lppro']):
                        suggested = h
                        break
                        
            if not suggested and all_hw:
                suggested = all_hw[0]
                
            g['suggested_hardware'] = suggested or g['name']
            result.append(g)
            
        return result

    def generate_hardware_report(self):
        """Génère un rapport textuel et structuré détaillant les canaux assignés et les matériels détectés."""
        groups = self.get_channel_groups()
        hw_info = self.detect_available_hardware()
        
        project_name = os.path.basename(self.file_path) if self.file_path else "Projet non enregistré"
        
        lines = []
        lines.append("=" * 70)
        lines.append(f"RAPPORT D'ASSIGNATION HARDWARE & CANAUX MIDI")
        lines.append(f"Projet : {project_name}")
        lines.append(f"Version Ableton : {self.creator}")
        lines.append("=" * 70)
        lines.append("")
        
        if not groups:
            lines.append("Aucun mapping de contrôleur physique n'a été détecté dans cette session.")
        else:
            lines.append("CANAUX MIDI ASSIGNÉS ET MATÉRIELS DÉTECTÉS :")
            lines.append("-" * 70)
            for g in groups:
                ch = g['channel']
                cnt = g['count']
                curr_name = g['name']
                sugg = g.get('suggested_hardware', curr_name)
                ccs = f"CC {min(g['ccs_summary'])} à {max(g['ccs_summary'])}" if g.get('ccs_summary') else "N/A"
                usage = ", ".join(g.get('params', []))
                
                lines.append(f"• CANAL MIDI {ch}  ({cnt} assignation{'s' if cnt > 1 else ''})")
                lines.append(f"  └─ Nom actuel       : {curr_name}")
                lines.append(f"  └─ Matériel suggéré : {sugg}")
                lines.append(f"  └─ Contrôleurs CC   : {ccs}")
                lines.append(f"  └─ Paramètres cibles: {usage}")
                lines.append("")
                
        lines.append("-" * 70)
        lines.append("PÉRIPHÉRIQUES ET SURFACES DÉTECTÉS DANS LIVE & WINDOWS :")
        if hw_info['surfaces']:
            lines.append("• Surfaces de contrôle configurées dans Ableton Live :")
            for s in hw_info['surfaces']:
                lines.append(f"   - {s}")
        if hw_info['devices']:
            lines.append("• Périphériques MIDI USB / Cartes son détectés :")
            for d in hw_info['devices']:
                lines.append(f"   - {d}")
        if not hw_info['surfaces'] and not hw_info['devices']:
            lines.append("• Aucun périphérique MIDI externe ou surface de contrôle détecté.")
        lines.append("=" * 70)
        
        report_text = "\n".join(lines)
        return {
            'text': report_text,
            'groups': groups,
            'hw_info': hw_info
        }

    # ==================== CHARGEMENT DE PROJET ====================
    def load_project(self, file_path):
        """Charge le projet Ableton (.als) compressé en GZIP et parse le XML."""
        self.file_path = file_path
        with gzip.open(self.file_path, 'rb') as f:
            xml_data = f.read()
        self.root = ET.fromstring(xml_data)
        self.tree = ET.ElementTree(self.root)
        self.creator = self.root.attrib.get('Creator', 'Ableton Live')
        self._build_param_lookup()
        self._mappings_cache = self._extract_all_mappings()

    def _build_param_lookup(self):
        """Construit un dictionnaire de résolution des IDs d'objets (Pistes, Périphériques, Paramètres)."""
        self.param_lookup.clear()
        if self.root is None:
            return
            
        parent_map = {c: p for p in self.root.iter() for c in p}
        for elem in self.root.iter():
            elem_id = elem.attrib.get('Id')
            if not elem_id or elem.tag == 'MidiNoteEvent':
                continue
            curr = elem
            p_elem = parent_map.get(elem)
            param_name = p_elem.tag if p_elem is not None else None
            device_name = None
            track_name = None
            
            while curr in parent_map:
                p = parent_map[curr]
                if device_name is None and p.tag == 'Devices':
                    un = curr.find('.//UserName')
                    if un is None or not un.get('Value'):
                        un = curr.find('.//EffectiveName')
                    device_name = un.get('Value') if un is not None and un.get('Value') else curr.tag
                if track_name is None and curr.tag.endswith('Track'):
                    tn = curr.find('.//Name/EffectiveName')
                    if tn is None or not tn.get('Value'):
                        tn = curr.find('.//EffectiveName')
                    track_name = tn.get('Value') if tn is not None and tn.get('Value') else curr.tag
                curr = p
                    
            parts = []
            if track_name:
                parts.append(f"Piste: {track_name}")
            if device_name:
                parts.append(f"Appareil: {device_name}")
            if param_name and param_name != device_name:
                parts.append(f"Param: {param_name}")
            self.param_lookup[elem_id] = " | ".join(parts) if parts else f"ID: {elem_id}"

    def get_summary(self):
        """Retourne les métriques clés du projet (pistes, clips, notes, mappings)."""
        if self.root is None:
            return {'tracks': 0, 'midi_tracks': 0, 'clips': 0, 'notes': 0, 'mappings': 0, 'creator': ''}
        tracks = self.get_tracks()
        midi_tracks = [t for t in tracks if t['is_midi']]
        clips = self.get_clips()
        notes = self.get_midi_notes()
        mappings = self.get_mappings()
        return {
            'tracks': len(tracks),
            'midi_tracks': len(midi_tracks),
            'clips': len(clips),
            'notes': len(notes),
            'mappings': len(mappings),
            'creator': self.creator
        }

    # ==================== EXTRACTION DES MAPPINGS CONTROLEURS ====================
    def _extract_all_mappings(self):
        """Extrait tous les mappings de contrôleurs physiques du projet avec nom de matériel."""
        mappings = []
        if self.root is None:
            return mappings
            
        parent_map = {c: p for p in self.root.iter() for c in p}
        
        # 1. Mappings natifs Ableton Live via KeyMidi (Live 9, 10, 11, 12)
        for km in self.root.iter('KeyMidi'):
            ch_elem = km.find('Channel')
            noc_elem = km.find('NoteOrController')
            is_note_elem = km.find('IsNote')
            
            if ch_elem is None or noc_elem is None:
                continue
                
            ch_val = ch_elem.get('Value', '0')
            noc_val = noc_elem.get('Value', '0')
            is_note_val = is_note_elem.get('Value', 'false') if is_note_elem is not None else 'false'
            
            # Exclure les macros internes des racks Ableton (Canal 16 en XML)
            if ch_val == '16':
                continue
                
            # Canal MIDI : en XML 0 = Canal 1, 15 = Canal 16
            try:
                midi_channel = str(int(ch_val) + 1)
            except ValueError:
                midi_channel = ch_val
                
            parent = parent_map.get(km)
            parent_tag = parent.tag if parent is not None else "Inconnu"
            
            # Nom précis du paramètre
            param_name = parent_tag
            if parent is not None:
                un = parent.find('.//UserName')
                if un is None or not un.get('Value'):
                    un = parent.find('.//EffectiveName')
                if un is not None and un.get('Value'):
                    param_name = f"{parent_tag} ({un.get('Value')})"
                elif parent_tag == 'ParameterValue':
                    gp = parent_map.get(parent)
                    if gp is not None:
                        pn = gp.find('ParameterName')
                        if pn is not None and pn.get('Value'):
                            param_name = pn.get('Value')
                            
            # Remonter pour trouver la Piste et l'Appareil (Device)
            curr = km
            track_name = ""
            device_name = ""
            while curr in parent_map:
                p = parent_map[curr]
                if not device_name and p.tag == 'Devices':
                    dun = curr.find('.//UserName')
                    if dun is None or not dun.get('Value'):
                        dun = curr.find('.//EffectiveName')
                    device_name = dun.get('Value') if (dun is not None and dun.get('Value')) else curr.tag
                if not track_name and curr.tag.endswith('Track'):
                    tn = curr.find('.//Name/EffectiveName')
                    if tn is None or not tn.get('Value'):
                        tn = curr.find('.//EffectiveName')
                    track_name = tn.get('Value') if tn is not None and tn.get('Value') else curr.tag
                curr = p
                
            track_name = track_name or "Master / Global"
            if not device_name and parent_tag in ['Mixer', 'Volume', 'Pan', 'Send', 'Speaker']:
                device_name = "Mixer"
                
            # Plage Min / Max
            min_val = "N/A"
            max_val = "N/A"
            if parent is not None:
                mcr = parent.find('MidiControllerRange')
                if mcr is not None:
                    mn = mcr.find('Min')
                    mx = mcr.find('Max')
                    if mn is not None: min_val = mn.get('Value')
                    if mx is not None: max_val = mx.get('Value')
                    
            m_type = 'Note' if is_note_val.lower() == 'true' else 'CC'
            mapping_id = f"KM-{len(mappings)+1}"
            
            desc_parts = [f"Piste: {track_name}"]
            if device_name:
                desc_parts.append(f"Appareil: {device_name}")
            desc_parts.append(f"Param: {param_name}")
            
            # Nom de matériel résolu depuis le profil ou par défaut
            hw_name = self.hardware_aliases.get(midi_channel, f"Contrôleur Ch. {midi_channel}")
            
            mappings.append({
                'id': mapping_id,
                'source': 'KeyMidi',
                'track': track_name,
                'device': device_name,
                'param': param_name,
                'type': m_type,
                'channel': midi_channel,
                'cc': noc_val,
                'hardware_name': hw_name,
                'target_desc': " | ".join(desc_parts),
                'min': min_val,
                'max': max_val,
                '_key_midi': km,
                '_parent': parent
            })
            
        # 2. Prise en charge complémentaire des balises MidiMappingRange / MidiMappingOnOff
        for tag in ['MidiMappingRange', 'MidiMappingOnOff']:
            for mapping in self.root.iter(tag):
                id_elem = mapping.find('Id')
                channel_elem = mapping.find('MidiControllerChannel')
                cc_elem = mapping.find('MidiControllerNumber')
                target_elem = mapping.find('RangeTarget') or mapping.find('Target')
                lockable_param = target_elem.find('LockableParameter') if target_elem is not None else None
                min_elem = target_elem.find('Min') if target_elem is not None else None
                max_elem = target_elem.find('Max') if target_elem is not None else None
                
                if id_elem is not None and channel_elem is not None and cc_elem is not None:
                    raw_target_id = lockable_param.get('Id') if lockable_param is not None else "Unknown"
                    target_desc = self.param_lookup.get(raw_target_id, f"ID: {raw_target_id}")
                    try:
                        midi_ch = str(int(channel_elem.get('Value')) + 1)
                    except ValueError:
                        midi_ch = channel_elem.get('Value')
                        
                    mapping_id = f"MM-{id_elem.get('Value')}"
                    hw_name = self.hardware_aliases.get(midi_ch, f"Contrôleur Ch. {midi_ch}")
                    mappings.append({
                        'id': mapping_id,
                        'source': tag,
                        'track': 'Projet',
                        'device': '',
                        'param': '',
                        'type': 'CC (Range)' if tag == 'MidiMappingRange' else 'Note/Bouton',
                        'channel': midi_ch,
                        'cc': cc_elem.get('Value'),
                        'hardware_name': hw_name,
                        'target_desc': target_desc,
                        'min': min_elem.get('Value') if min_elem is not None else "N/A",
                        'max': max_elem.get('Value') if max_elem is not None else "N/A",
                        '_elem': mapping
                    })
                    
        return mappings

    def get_mappings(self, track_name=None, hardware_name=None):
        """Récupère les mappings de contrôleurs extraits, avec filtrage optionnel."""
        if not self._mappings_cache:
            self._mappings_cache = self._extract_all_mappings()
            
        result = list(self._mappings_cache)
        if track_name and track_name != "Toutes les pistes":
            result = [m for m in result if m['track'] == track_name]
        if hardware_name and hardware_name != "Tous les matériels":
            result = [m for m in result if m['hardware_name'] == hardware_name]
        return result

    def update_mapping(self, mapping_id_or_dict, new_channel, new_cc, new_min=None, new_max=None):
        """Met à jour un mapping (Canal MIDI, Note/CC, Min, Max) dans l'arbre XML Ableton."""
        m_item = None
        if isinstance(mapping_id_or_dict, dict):
            m_item = mapping_id_or_dict
        else:
            for m in self._mappings_cache:
                if str(m['id']) == str(mapping_id_or_dict):
                    m_item = m
                    break
                    
        if m_item is None:
            return False
            
        if m_item.get('source') == 'KeyMidi':
            km = m_item.get('_key_midi')
            if km is None:
                return False
                
            try:
                xml_ch = str(max(0, min(15, int(new_channel) - 1)))
            except ValueError:
                xml_ch = str(new_channel)
                
            ch_elem = km.find('Channel')
            if ch_elem is not None:
                ch_elem.set('Value', xml_ch)
                
            noc_elem = km.find('NoteOrController')
            if noc_elem is not None:
                noc_elem.set('Value', str(new_cc))
                
            parent = m_item.get('_parent')
            if parent is not None:
                mcr = parent.find('MidiControllerRange')
                if mcr is not None:
                    if new_min is not None and new_min != "N/A":
                        mn = mcr.find('Min')
                        if mn is not None: mn.set('Value', str(new_min))
                    if new_max is not None and new_max != "N/A":
                        mx = mcr.find('Max')
                        if mx is not None: mx.set('Value', str(new_max))
                        
            m_item['channel'] = str(new_channel)
            m_item['cc'] = str(new_cc)
            m_item['hardware_name'] = self.hardware_aliases.get(str(new_channel), f"Contrôleur Ch. {new_channel}")
            if new_min is not None and new_min != "N/A": m_item['min'] = str(new_min)
            if new_max is not None and new_max != "N/A": m_item['max'] = str(new_max)
            return True
            
        else:
            mapping_elem = m_item.get('_elem')
            if mapping_elem is None:
                return False
                
            try:
                xml_ch = str(max(0, min(15, int(new_channel) - 1)))
            except ValueError:
                xml_ch = str(new_channel)
                
            ch_elem = mapping_elem.find('MidiControllerChannel')
            if ch_elem is not None:
                ch_elem.set('Value', xml_ch)
                
            cc_elem = mapping_elem.find('MidiControllerNumber')
            if cc_elem is not None:
                cc_elem.set('Value', str(new_cc))
                
            target_elem = mapping_elem.find('RangeTarget') or mapping_elem.find('Target')
            if target_elem is not None:
                if new_min is not None and new_min != "N/A":
                    mn = target_elem.find('Min')
                    if mn is not None: mn.set('Value', str(new_min))
                if new_max is not None and new_max != "N/A":
                    mx = target_elem.find('Max')
                    if mx is not None: mx.set('Value', str(new_max))
                    
            m_item['channel'] = str(new_channel)
            m_item['cc'] = str(new_cc)
            m_item['hardware_name'] = self.hardware_aliases.get(str(new_channel), f"Contrôleur Ch. {new_channel}")
            if new_min is not None and new_min != "N/A": m_item['min'] = str(new_min)
            if new_max is not None and new_max != "N/A": m_item['max'] = str(new_max)
            return True

    def delete_mapping(self, mapping_item):
        """Supprime une assignation de contrôleur (détache le mapping du paramètre dans Live)."""
        if mapping_item.get('source') == 'KeyMidi':
            km = mapping_item.get('_key_midi')
            parent = mapping_item.get('_parent')
            if km is not None and parent is not None and km in parent:
                parent.remove(km)
                if mapping_item in self._mappings_cache:
                    self._mappings_cache.remove(mapping_item)
                return True
        else:
            elem = mapping_item.get('_elem')
            if elem is not None and self.root is not None:
                parent_map = {c: p for p in self.root.iter() for c in p}
                p = parent_map.get(elem)
                if p is not None and elem in p:
                    p.remove(elem)
                    if mapping_item in self._mappings_cache:
                        self._mappings_cache.remove(mapping_item)
                    return True
        return False

    # ==================== GESTION DES PISTES & CLIPS ====================
    def get_tracks(self):
        """Récupère toutes les pistes du projet avec leur type et leur nom."""
        tracks = []
        if self.root is None:
            return tracks
        tracks_node = self.root.find('.//Tracks')
        if tracks_node is None:
            return tracks
        for idx, t in enumerate(tracks_node):
            tn = t.find('.//Name/EffectiveName')
            if tn is None or not tn.get('Value'):
                tn = t.find('.//EffectiveName')
            name = tn.get('Value') if tn is not None and tn.get('Value') else f"Piste {idx+1}"
            tracks.append({
                'index': idx,
                'type': t.tag,
                'name': name,
                'is_midi': t.tag == 'MidiTrack',
                'element': t
            })
        return tracks

    def get_clips(self, track_idx=None):
        """Récupère tous les clips MIDI du projet ou d'une piste spécifique."""
        clips = []
        tracks = self.get_tracks()
        for t_info in tracks:
            if track_idx is not None and t_info['index'] != track_idx:
                continue
            t_elem = t_info['element']
            for c_idx, clip in enumerate(t_elem.iter('MidiClip')):
                c_name = clip.find('Name')
                name = c_name.get('Value') if (c_name is not None and c_name.get('Value')) else f"Clip {c_idx+1}"
                notes = clip.findall('.//MidiNoteEvent')
                c_id = clip.get('Id', str(c_idx))
                clips.append({
                    'clip_id': c_id,
                    'clip_index': c_idx,
                    'clip_name': name,
                    'track_index': t_info['index'],
                    'track_name': t_info['name'],
                    'notes_count': len(notes),
                    'element': clip
                })
        return clips

    # ==================== GESTION DES NOTES MIDI ====================
    def get_midi_notes(self, track_idx=None, clip_id=None):
        """Récupère tous les événements de notes MIDI avec hauteur, position, durée, vélocité."""
        notes = []
        clips = self.get_clips(track_idx=track_idx)
        for c_info in clips:
            if clip_id is not None and str(c_info['clip_id']) != str(clip_id):
                continue
            clip_elem = c_info['element']
            key_tracks = clip_elem.findall('.//KeyTracks/KeyTrack')
            for kt in key_tracks:
                mk = kt.find('MidiKey')
                pitch = int(mk.get('Value')) if (mk is not None and mk.get('Value')) else 60
                notes_container = kt.find('Notes')
                if notes_container is None:
                    continue
                for note_elem in notes_container.findall('MidiNoteEvent'):
                    t = float(note_elem.get('Time', 0))
                    d = float(note_elem.get('Duration', 0))
                    v = float(note_elem.get('Velocity', 100))
                    p = float(note_elem.get('Probability', 1))
                    enabled = note_elem.get('IsEnabled', 'true').lower() == 'true'
                    nid = note_elem.get('NoteId', '')
                    notes.append({
                        'track_name': c_info['track_name'],
                        'track_index': c_info['track_index'],
                        'clip_name': c_info['clip_name'],
                        'clip_id': c_info['clip_id'],
                        'pitch': pitch,
                        'note_name': midi_pitch_to_name(pitch),
                        'time': t,
                        'duration': d,
                        'velocity': v,
                        'probability': p,
                        'is_enabled': enabled,
                        'note_id': nid,
                        '_elem': note_elem,
                        '_key_track': kt,
                        '_clip_elem': clip_elem
                    })
        notes.sort(key=lambda n: (n['track_index'], n['clip_name'], n['time'], n['pitch']))
        return notes

    def update_midi_note(self, note_item, new_pitch=None, new_time=None, new_duration=None, new_velocity=None, new_enabled=None):
        """Met à jour un événement de note MIDI dans l'arbre XML Ableton."""
        elem = note_item['_elem']
        kt = note_item['_key_track']
        clip_elem = note_item['_clip_elem']
        
        # 1. Hauteur (pitch)
        if new_pitch is not None:
            target_pitch = note_name_to_pitch(new_pitch)
            if target_pitch is not None and target_pitch != note_item['pitch']:
                old_notes = kt.find('Notes')
                if old_notes is not None and elem in old_notes:
                    old_notes.remove(elem)
                    if len(old_notes) == 0:
                        key_tracks_parent = clip_elem.find('.//KeyTracks')
                        if key_tracks_parent is not None and kt in key_tracks_parent:
                            key_tracks_parent.remove(kt)
                
                key_tracks_parent = clip_elem.find('.//KeyTracks')
                if key_tracks_parent is None:
                    notes_tag = clip_elem.find('Notes')
                    if notes_tag is None:
                        notes_tag = ET.SubElement(clip_elem, 'Notes')
                    key_tracks_parent = ET.SubElement(notes_tag, 'KeyTracks')
                
                target_kt = None
                for k in key_tracks_parent.findall('KeyTrack'):
                    mk = k.find('MidiKey')
                    if mk is not None and mk.get('Value') == str(target_pitch):
                        target_kt = k
                        break
                
                if target_kt is None:
                    existing_ids = [int(k.get('Id', 0)) for k in key_tracks_parent.findall('KeyTrack') if k.get('Id', '').isdigit()]
                    next_id = max(existing_ids, default=0) + 1
                    target_kt = ET.SubElement(key_tracks_parent, 'KeyTrack', {'Id': str(next_id)})
                    new_notes = ET.SubElement(target_kt, 'Notes')
                    ET.SubElement(target_kt, 'MidiKey', {'Value': str(target_pitch)})
                else:
                    new_notes = target_kt.find('Notes')
                    if new_notes is None:
                        new_notes = ET.SubElement(target_kt, 'Notes')
                
                new_notes.append(elem)
                note_item['_key_track'] = target_kt
                note_item['pitch'] = target_pitch
                note_item['note_name'] = midi_pitch_to_name(target_pitch)
        
        # 2. Position temporelle (Time)
        if new_time is not None:
            try:
                t_val = round(max(0.0, float(new_time)), 4)
                elem.set('Time', str(t_val))
                note_item['time'] = t_val
            except ValueError:
                pass
                
        # 3. Durée (Duration)
        if new_duration is not None:
            try:
                d_val = round(max(0.01, float(new_duration)), 4)
                elem.set('Duration', str(d_val))
                note_item['duration'] = d_val
            except ValueError:
                pass
                
        # 4. Vélocité
        if new_velocity is not None:
            try:
                v_val = round(max(1.0, min(127.0, float(new_velocity))), 1)
                elem.set('Velocity', str(v_val))
                note_item['velocity'] = v_val
            except ValueError:
                pass
                
        # 5. Statut actif / muet
        if new_enabled is not None:
            is_en = bool(new_enabled)
            elem.set('IsEnabled', 'true' if is_en else 'false')
            note_item['is_enabled'] = is_en
            
        return True

    def delete_midi_note(self, note_item):
        """Supprime un événement de note MIDI du clip."""
        elem = note_item['_elem']
        kt = note_item['_key_track']
        clip_elem = note_item['_clip_elem']
        notes_container = kt.find('Notes')
        if notes_container is not None and elem in notes_container:
            notes_container.remove(elem)
            if len(notes_container) == 0:
                key_tracks_parent = clip_elem.find('.//KeyTracks')
                if key_tracks_parent is not None and kt in key_tracks_parent:
                    key_tracks_parent.remove(kt)
            return True
        return False

    def batch_transpose(self, notes_list, semitones):
        """Transpose un ensemble de notes de +/- X demi-tons."""
        for n in notes_list:
            new_pitch = max(0, min(127, n['pitch'] + semitones))
            self.update_midi_note(n, new_pitch=new_pitch)

    def batch_velocity(self, notes_list, delta=None, fixed_val=None):
        """Modifie la vélocité d'un ensemble de notes (+/- delta ou valeur fixe)."""
        for n in notes_list:
            if fixed_val is not None:
                new_v = max(1, min(127, fixed_val))
            elif delta is not None:
                new_v = max(1, min(127, n['velocity'] + delta))
            else:
                continue
            self.update_midi_note(n, new_velocity=new_v)

    def batch_set_active(self, notes_list, is_enabled):
        """Active ou coupe (mute) un ensemble de notes."""
        for n in notes_list:
            self.update_midi_note(n, new_enabled=is_enabled)

    # ==================== EXPORT & TEMPLATES ====================
    def export_project(self, output_path):
        """Regénère le fichier .als compressé en GZIP avec l'arbre XML mis à jour."""
        if self.root is None:
            return
        xml_str = ET.tostring(self.root, encoding='utf-8', xml_declaration=True)
        with gzip.open(output_path, 'wb') as f:
            f.write(xml_str)

    def save_template(self, output_path):
        """Sauvegarde les mappings actuels et les alias matériels sous forme de profil JSON."""
        mappings = self.get_mappings()
        export_data = {
            'hardware_profiles': self.hardware_aliases,
            'mappings': []
        }
        for m in mappings:
            export_data['mappings'].append({
                'track': m.get('track', ''),
                'device': m.get('device', ''),
                'param': m.get('param', ''),
                'type': m.get('type', 'CC'),
                'channel': m.get('channel', '1'),
                'cc': m.get('cc', '0'),
                'hardware_name': m.get('hardware_name', ''),
                'min': m.get('min', 'N/A'),
                'max': m.get('max', 'N/A'),
                'target_desc': m.get('target_desc', '')
            })
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=4, ensure_ascii=False)

    def load_template(self, template_path):
        """Applique un profil JSON en réassignant Canal, CC, Min et Max par correspondance de paramètres."""
        with open(template_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        template_mappings = raw_data.get('mappings', raw_data) if isinstance(raw_data, dict) else raw_data
        if isinstance(raw_data, dict) and 'hardware_profiles' in raw_data:
            self.save_hardware_aliases(raw_data['hardware_profiles'])
            
        current_mappings = self.get_mappings()
        applied_count = 0
        
        for tpl in template_mappings:
            target_track = tpl.get('track')
            target_param = tpl.get('param')
            
            for cur in current_mappings:
                match = False
                if target_track and target_param:
                    if cur.get('track') == target_track and cur.get('param') == target_param:
                        match = True
                elif tpl.get('target_desc') and cur.get('target_desc') == tpl.get('target_desc'):
                    match = True
                    
                if match:
                    self.update_mapping(
                        cur,
                        new_channel=tpl.get('channel', cur.get('channel')),
                        new_cc=tpl.get('cc', cur.get('cc')),
                        new_min=tpl.get('min', cur.get('min')),
                        new_max=tpl.get('max', cur.get('max'))
                    )
                    applied_count += 1
                    break
                    
        return applied_count

    def export_notes_to_json(self, output_path, track_idx=None, clip_id=None):
        """Exporte les événements de notes MIDI extraits vers un fichier JSON structuré."""
        notes = self.get_midi_notes(track_idx=track_idx, clip_id=clip_id)
        serializable_notes = []
        for n in notes:
            serializable_notes.append({
                'track_name': n['track_name'],
                'clip_name': n['clip_name'],
                'pitch': n['pitch'],
                'note_name': n['note_name'],
                'time': n['time'],
                'duration': n['duration'],
                'velocity': n['velocity'],
                'probability': n['probability'],
                'is_enabled': n['is_enabled']
            })
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_notes, f, indent=4, ensure_ascii=False)
