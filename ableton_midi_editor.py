import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from ableton_parser import AbletonMidiEditor, midi_pitch_to_name, note_name_to_pitch

# Configuration de l'apparence selon les DAW (Thème Sombre)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HardwareReportDialog(ctk.CTkToplevel):
    """Fenêtre affichant le rapport détaillé de détection des canaux assignés et du matériel."""
    def __init__(self, parent, editor, on_apply_callback=None):
        super().__init__(parent)
        self.title("🔍 Rapport de Détection des Contrôleurs & Canaux")
        self.geometry("760x600")
        self.minsize(660, 460)
        self.editor = editor
        self.on_apply_callback = on_apply_callback
        
        self.transient(parent)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # En-tête explicatif
        hdr = ctk.CTkFrame(self, fg_color="#1e1e24", corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        
        lbl_title = ctk.CTkLabel(hdr, text="🔍 Canaux Assignés & Contrôleurs Détectés", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_title.pack(anchor="w", padx=20, pady=(12, 3))
        
        lbl_desc = ctk.CTkLabel(
            hdr,
            text="Ce rapport croise vos mappings MIDI réels avec les surfaces de contrôle et périphériques USB détectés.\nVous pouvez copier ces informations ou les appliquer directement à votre projet.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(0, 10))
        
        # Zone de texte avec le rapport complet
        self.report_data = self.editor.generate_hardware_report()
        
        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12), wrap="none")
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.textbox.insert("1.0", self.report_data['text'])
        self.textbox.configure(state="disabled")
        
        # Barre d'actions inférieure
        bottom_bar = ctk.CTkFrame(self, fg_color="transparent")
        bottom_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))
        
        self.btn_copy = ctk.CTkButton(
            bottom_bar,
            text="📋 Copier le Rapport (Presse-Papier)",
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(weight="bold"),
            command=self._copy_to_clipboard
        )
        self.btn_copy.pack(side="left", padx=5)
        
        if self.on_apply_callback:
            self.btn_apply = ctk.CTkButton(
                bottom_bar,
                text="⚡ Appliquer les Noms Suggérés",
                fg_color="#0d9488",
                hover_color="#0f766e",
                font=ctk.CTkFont(weight="bold"),
                command=self._apply_and_close
            )
            self.btn_apply.pack(side="left", padx=5)
            
        self.btn_close = ctk.CTkButton(bottom_bar, text="Fermer", fg_color="gray40", hover_color="gray50", command=self.destroy)
        self.btn_close.pack(side="right", padx=5)
        
    def _copy_to_clipboard(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.report_data['text'])
            self.update()
            self.btn_copy.configure(text="✔ Copié dans le Presse-Papier !")
            self.after(2000, lambda: self.btn_copy.configure(text="📋 Copier le Rapport (Presse-Papier)"))
        except Exception:
            pass

    def _apply_and_close(self):
        if self.on_apply_callback:
            suggestions = {g['channel']: g.get('suggested_hardware', g['name']) for g in self.report_data['groups']}
            self.on_apply_callback(suggestions)
        self.destroy()


class HardwareNamingDialog(ctk.CTkToplevel):
    """Fenêtre modale permettant de détecter et d'associer un nom de matériel à chaque canal MIDI."""
    def __init__(self, parent, editor, channel_groups, on_save_callback):
        super().__init__(parent)
        self.title("🏷️ Identifier mes Contrôleurs Hardware")
        self.geometry("860x590")
        self.minsize(740, 460)
        self.editor = editor
        self.channel_groups = channel_groups
        self.on_save_callback = on_save_callback
        self.detected_hardware = []
        
        self.transient(parent)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # --- 1. En-tête explicatif ---
        header_frame = ctk.CTkFrame(self, fg_color="#1e1e24", corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        
        title_lbl = ctk.CTkLabel(header_frame, text="Association Canaux MIDI ⇄ Contrôleurs Hardware", font=ctk.CTkFont(size=16, weight="bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(12, 3))
        
        desc_lbl = ctk.CTkLabel(
            header_frame, 
            text="Ableton Live enregistre les assignations physiques par Canal MIDI (1 à 16). Utilisez le bouton de détection\npour identifier vos appareils Live ou récupérer automatiquement leurs noms en 1 clic.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            justify="left"
        )
        desc_lbl.pack(anchor="w", padx=20, pady=(0, 10))
        
        # --- 2. Barre d'action : Détection & Outils ---
        detect_bar = ctk.CTkFrame(self, fg_color="#24242c", corner_radius=6)
        detect_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        
        self.btn_detect = ctk.CTkButton(
            detect_bar, 
            text="🔍 Détecter Contrôleurs Live & Windows", 
            fg_color="#0284c7", 
            hover_color="#0369a1", 
            font=ctk.CTkFont(weight="bold", size=12),
            height=32,
            command=self._run_hardware_detection
        )
        self.btn_detect.pack(side="left", padx=(10, 5), pady=8)

        self.btn_report = ctk.CTkButton(
            detect_bar,
            text="📋 Rapport Détaillé",
            fg_color="#475569",
            hover_color="#334155",
            font=ctk.CTkFont(weight="bold", size=12),
            height=32,
            command=self._open_report_dialog
        )
        self.btn_report.pack(side="left", padx=5, pady=8)
        
        self.btn_autofill = ctk.CTkButton(
            detect_bar,
            text="⚡ Auto-remplir les Suggestions",
            fg_color="#0d9488",
            hover_color="#0f766e",
            font=ctk.CTkFont(weight="bold", size=12),
            height=32,
            command=self._apply_smart_suggestions
        )
        self.btn_autofill.pack(side="left", padx=5, pady=8)

        self.btn_copy_summary = ctk.CTkButton(
            detect_bar,
            text="📋 Copier Récap",
            fg_color="#6366f1",
            hover_color="#4f46e5",
            font=ctk.CTkFont(weight="bold", size=12),
            height=32,
            command=self._copy_summary_to_clipboard
        )
        self.btn_copy_summary.pack(side="left", padx=5, pady=8)
        
        self.detect_status_lbl = ctk.CTkLabel(
            detect_bar,
            text="Scan automatique des appareils...",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="gray70"
        )
        self.detect_status_lbl.pack(side="left", padx=10, pady=8)
        
        # --- 3. Liste déroulante des canaux de la session ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Canaux Détectés dans la Session Active", label_font=ctk.CTkFont(weight="bold"))
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)
        self.scroll_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        
        # En-têtes du tableau
        hdr_ch = ctk.CTkLabel(self.scroll_frame, text="Canal MIDI", font=ctk.CTkFont(weight="bold", size=12), anchor="w")
        hdr_ch.grid(row=0, column=0, padx=6, pady=4, sticky="w")
        
        hdr_usage = ctk.CTkLabel(self.scroll_frame, text="Usage Détecté (CCs & Paramètres)", font=ctk.CTkFont(weight="bold", size=12), anchor="w")
        hdr_usage.grid(row=0, column=1, padx=6, pady=4, sticky="w")
        
        hdr_name = ctk.CTkLabel(self.scroll_frame, text="Nom Attribué", font=ctk.CTkFont(weight="bold", size=12), anchor="w")
        hdr_name.grid(row=0, column=2, padx=6, pady=4, sticky="w")
        
        hdr_picker = ctk.CTkLabel(self.scroll_frame, text="Matériel Détecté / Choix", font=ctk.CTkFont(weight="bold", size=12), anchor="w")
        hdr_picker.grid(row=0, column=3, padx=6, pady=4, sticky="w")

        hdr_action = ctk.CTkLabel(self.scroll_frame, text="Action Rapide", font=ctk.CTkFont(weight="bold", size=12))
        hdr_action.grid(row=0, column=4, padx=6, pady=4)
        
        self.entries = {}
        self.pickers = {}
        self.retrieve_btns = {}
        
        for i, g in enumerate(self.channel_groups, start=1):
            ch = g['channel']
            count = g['count']
            current_name = g['name']
            suggested = g.get('suggested_hardware', current_name)
            usage_str = ", ".join(g['params'][:2])
            if len(g['params']) > 2:
                usage_str += "..."
            ccs_str = f"CC: {min(g['ccs_summary'])}-{max(g['ccs_summary'])}" if g['ccs_summary'] else ""
            
            # Badge canal
            lbl_ch = ctk.CTkLabel(
                self.scroll_frame, 
                text=f"Canal {ch} ({count} assigns)", 
                font=ctk.CTkFont(weight="bold", size=12),
                anchor="w"
            )
            lbl_ch.grid(row=i, column=0, padx=6, pady=6, sticky="w")
            
            # Détails d'usage
            lbl_details = ctk.CTkLabel(
                self.scroll_frame,
                text=f"{ccs_str} • {usage_str}",
                font=ctk.CTkFont(size=11),
                text_color="gray70",
                anchor="w"
            )
            lbl_details.grid(row=i, column=1, padx=6, pady=6, sticky="w")
            
            # Champ de saisie
            entry_var = ctk.StringVar(value=current_name)
            entry = ctk.CTkEntry(self.scroll_frame, textvariable=entry_var, placeholder_text="Nom du contrôleur...", width=160)
            entry.grid(row=i, column=2, padx=6, pady=6, sticky="ew")
            self.entries[ch] = entry_var
            
            # Menu déroulant de sélection rapide
            initial_val = suggested if suggested else "Choisir... ▼"
            picker_var = ctk.StringVar(value=initial_val)
            picker = ctk.CTkOptionMenu(
                self.scroll_frame, 
                values=[initial_val, "Choisir... ▼"], 
                width=160,
                command=lambda val, ch_id=ch: self._on_hardware_picked(ch_id, val)
            )
            picker.grid(row=i, column=3, padx=6, pady=6, sticky="ew")
            self.pickers[ch] = picker

            # Bouton de récupération rapide / copie
            btn_get = ctk.CTkButton(
                self.scroll_frame,
                text="⬅ Récupérer",
                width=90,
                height=28,
                fg_color="#3b82f6",
                hover_color="#2563eb",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda ch_id=ch: self._retrieve_hardware_name(ch_id)
            )
            btn_get.grid(row=i, column=4, padx=6, pady=6)
            self.retrieve_btns[ch] = btn_get
            
        # --- 4. Boutons d'action bas de page ---
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=12)
        
        save_btn = ctk.CTkButton(bottom_frame, text="💾 Enregistrer et Appliquer", fg_color="#28a745", hover_color="#218838", font=ctk.CTkFont(weight="bold"), command=self._save_and_close)
        save_btn.pack(side="right", padx=5)
        
        cancel_btn = ctk.CTkButton(bottom_frame, text="Annuler", fg_color="gray40", hover_color="gray50", command=self.destroy)
        cancel_btn.pack(side="right", padx=5)

        # Exécuter la détection automatiquement dès l'ouverture
        self._run_hardware_detection()

    def _run_hardware_detection(self):
        """Exécute la détection des appareils dans Ableton et met à jour l'interface."""
        hw_info = self.editor.detect_available_hardware()
        all_names = hw_info['all_names']
        self.detected_hardware = all_names
        
        if not all_names:
            self.detect_status_lbl.configure(
                text="Aucun contrôleur détecté dans les préférences Live.",
                text_color="#f59e0b"
            )
            return
            
        summary_text = f"✅ {len(all_names)} matériels détectés : {', '.join(all_names[:3])}"
        if len(all_names) > 3:
            summary_text += f" (+{len(all_names)-3} autres)"
            
        self.detect_status_lbl.configure(text=summary_text, text_color="#38bdf8")
        
        # Mettre à jour les menus déroulants pour chaque canal
        picker_values = ["Choisir... ▼"] + all_names
        for ch, picker in self.pickers.items():
            curr = picker.get()
            picker.configure(values=picker_values)
            if curr in picker_values:
                picker.set(curr)

    def _retrieve_hardware_name(self, channel):
        """Récupère le nom du matériel sélectionné ou suggéré, le place dans le champ et le copie."""
        chosen = self.pickers[channel].get()
        if chosen == "Choisir... ▼" or not chosen:
            for g in self.channel_groups:
                if g['channel'] == channel:
                    chosen = g.get('suggested_hardware', '')
                    break
        if chosen and chosen != "Choisir... ▼":
            self.entries[channel].set(chosen)
            if channel in self.pickers:
                self.pickers[channel].set(chosen)
            try:
                self.clipboard_clear()
                self.clipboard_append(chosen)
                self.update()
            except Exception:
                pass
            btn = self.retrieve_btns.get(channel)
            if btn:
                btn.configure(text="✔ Copié !", fg_color="#10b981")
                self.after(1400, lambda b=btn: b.configure(text="⬅ Récupérer", fg_color="#3b82f6"))

    def _open_report_dialog(self):
        """Ouvre la boîte de dialogue avec le rapport textuel complet."""
        def on_apply(suggestions):
            for ch, name in suggestions.items():
                if ch in self.entries:
                    self.entries[ch].set(name)
                if ch in self.pickers and name in self.detected_hardware:
                    self.pickers[ch].set(name)
        HardwareReportDialog(self, self.editor, on_apply)

    def _copy_summary_to_clipboard(self):
        """Copie le rapport synthétique des canaux et matériels dans le presse-papier."""
        rep = self.editor.generate_hardware_report()
        try:
            self.clipboard_clear()
            self.clipboard_append(rep['text'])
            self.update()
            self.btn_copy_summary.configure(text="✔ Récap Copié !", fg_color="#10b981")
            self.after(1600, lambda: self.btn_copy_summary.configure(text="📋 Copier Récap", fg_color="#6366f1"))
        except Exception:
            pass

    def _apply_smart_suggestions(self):
        """Régit intelligemment les noms des canaux selon les détections d'Ableton."""
        if not self.detected_hardware:
            self._run_hardware_detection()
            
        for g in self.channel_groups:
            ch = g['channel']
            suggested = g.get('suggested_hardware')
            if suggested and ch in self.entries:
                self.entries[ch].set(suggested)
                if ch in self.pickers and suggested in self.detected_hardware:
                    self.pickers[ch].set(suggested)

    def _on_hardware_picked(self, channel, chosen_value):
        """Quand l'utilisateur sélectionne un appareil dans le menu déroulant, met à jour le champ texte."""
        if chosen_value != "Choisir... ▼" and channel in self.entries:
            self.entries[channel].set(chosen_value)

    def _save_and_close(self):
        result = {ch: var.get().strip() for ch, var in self.entries.items() if var.get().strip()}
        self.on_save_callback(result)
        self.destroy()


class AbletonMidiApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Éditeur de Mappings & Événements MIDI pour Ableton Live")
        self.geometry("1260x760")
        self.minsize(1100, 640)
        
        self.editor = AbletonMidiEditor()
        self.current_notes = []
        self.current_mappings = []
        self.notes_page = 0
        self.notes_page_size = 50
        
        # Configuration de la grille principale
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- Barre Latérale ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Ableton Live\nMIDI Control Studio", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 15))
        
        self.load_btn = ctk.CTkButton(self.sidebar, text="📂 Importer Projet (.als)", command=self.load_project, height=36, font=ctk.CTkFont(weight="bold"))
        self.load_btn.grid(row=1, column=0, padx=20, pady=8)
        
        self.export_btn = ctk.CTkButton(self.sidebar, text="💾 Régénérer & Exporter", command=self.export_project, state="disabled", fg_color="#28a745", hover_color="#218838", height=36, font=ctk.CTkFont(weight="bold"))
        self.export_btn.grid(row=2, column=0, padx=20, pady=8)
        
        sep = ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30")
        sep.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        
        self.save_tpl_btn = ctk.CTkButton(self.sidebar, text="💾 Sauver Profil Mappings", command=self.save_template, state="disabled", height=32)
        self.save_tpl_btn.grid(row=4, column=0, padx=20, pady=5)
        
        self.load_tpl_btn = ctk.CTkButton(self.sidebar, text="📂 Charger Profil Mappings", command=self.load_template, state="disabled", height=32)
        self.load_tpl_btn.grid(row=5, column=0, padx=20, pady=5)
        
        self.export_json_btn = ctk.CTkButton(self.sidebar, text="📄 Exporter Notes (JSON)", command=self.export_notes_json, state="disabled", fg_color="#17a2b8", hover_color="#138496", height=32)
        self.export_json_btn.grid(row=6, column=0, padx=20, pady=5)
        
        # Carte des Statistiques du Projet
        self.stats_frame = ctk.CTkFrame(self.sidebar, fg_color="#1e1e24", corner_radius=8)
        self.stats_frame.grid(row=7, column=0, padx=15, pady=(15, 10), sticky="ew")
        
        self.stats_title = ctk.CTkLabel(self.stats_frame, text="📊 Résumé de la Session", font=ctk.CTkFont(size=12, weight="bold"))
        self.stats_title.pack(anchor="w", padx=10, pady=(8, 4))
        
        self.stats_lbl_maps = ctk.CTkLabel(self.stats_frame, text="🎛️ Mappings Contrôleurs : -", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
        self.stats_lbl_maps.pack(anchor="w", padx=10, pady=2)
        self.stats_lbl_tracks = ctk.CTkLabel(self.stats_frame, text="🎵 Pistes MIDI : -", font=ctk.CTkFont(size=11), text_color="gray70")
        self.stats_lbl_tracks.pack(anchor="w", padx=10, pady=1)
        self.stats_lbl_clips = ctk.CTkLabel(self.stats_frame, text="🎼 Clips MIDI : -", font=ctk.CTkFont(size=11), text_color="gray70")
        self.stats_lbl_clips.pack(anchor="w", padx=10, pady=1)
        self.stats_lbl_notes = ctk.CTkLabel(self.stats_frame, text="🎹 Notes MIDI : -", font=ctk.CTkFont(size=11), text_color="gray70")
        self.stats_lbl_notes.pack(anchor="w", padx=10, pady=(1, 8))
        
        self.version_label = ctk.CTkLabel(self.sidebar, text="v2.2 • Hardware Auto-Detect", font=ctk.CTkFont(size=10), text_color="gray50")
        self.version_label.grid(row=10, column=0, padx=20, pady=10, sticky="s")
        
        # --- Zone Principale ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Bandeau de statut
        self.status_bar = ctk.CTkFrame(self.main_frame, height=40, fg_color="#1e1e24", corner_radius=6)
        self.status_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.status_label = ctk.CTkLabel(self.status_bar, text="Aucun projet chargé. Veuillez importer un fichier .als.", font=ctk.CTkFont(size=13, slant="italic"))
        self.status_label.pack(side="left", padx=15, pady=8)
        
        # Onglets principaux : Mappings Contrôleurs en 1er
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=1, column=0, sticky="nsew")
        
        self.tab_mappings = self.tabview.add("🎛️ Mappings Contrôleurs (Ctrl+M)")
        self.tab_notes = self.tabview.add("🎹 Événements & Notes MIDI")
        
        self._setup_mappings_tab()
        self._setup_notes_tab()

    # ==================== CONFIGURATION ONGLET MAPPINGS ====================
    def _setup_mappings_tab(self):
        self.tab_mappings.grid_columnconfigure(0, weight=1)
        self.tab_mappings.grid_rowconfigure(2, weight=1)
        
        # 1. Barre de Recherche et Filtres
        map_filter_bar = ctk.CTkFrame(self.tab_mappings, fg_color="#24242c", corner_radius=6)
        map_filter_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 8))
        
        # Bouton Nommer Matériels & Détection (mis en avant)
        self.btn_name_hardware = ctk.CTkButton(
            map_filter_bar, 
            text="🏷️ Nommer mes Contrôleurs...", 
            fg_color="#0284c7", 
            hover_color="#0369a1", 
            font=ctk.CTkFont(weight="bold", size=12),
            height=30,
            command=self._open_hardware_naming_dialog
        )
        self.btn_name_hardware.pack(side="left", padx=(10, 5), pady=8)
        
        self.btn_detect_hardware = ctk.CTkButton(
            map_filter_bar, 
            text="🔍 Détecter Matériels & Canaux", 
            fg_color="#0d9488", 
            hover_color="#0f766e", 
            font=ctk.CTkFont(weight="bold", size=12),
            height=30,
            command=self._open_hardware_report_dialog
        )
        self.btn_detect_hardware.pack(side="left", padx=(5, 10), pady=8)
        
        # Filtre Contrôleur Hardware
        ctk.CTkLabel(map_filter_bar, text="Matériel :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(5, 4), pady=8)
        self.map_hw_menu = ctk.CTkOptionMenu(map_filter_bar, values=["Tous les matériels"], command=self._on_map_filter_changed, width=160)
        self.map_hw_menu.pack(side="left", padx=4, pady=8)
        
        # Filtre Piste
        ctk.CTkLabel(map_filter_bar, text="Piste :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.map_track_menu = ctk.CTkOptionMenu(map_filter_bar, values=["Toutes les pistes"], command=self._on_map_filter_changed, width=140)
        self.map_track_menu.pack(side="left", padx=4, pady=8)
        
        # Filtre Type (CC / Note)
        ctk.CTkLabel(map_filter_bar, text="Type :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.map_type_menu = ctk.CTkOptionMenu(map_filter_bar, values=["Tous", "CC", "Note"], command=self._on_map_filter_changed, width=80)
        self.map_type_menu.pack(side="left", padx=4, pady=8)
        
        # Recherche texte
        ctk.CTkLabel(map_filter_bar, text="Recherche :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.map_search_var = ctk.StringVar()
        self.map_search_entry = ctk.CTkEntry(map_filter_bar, textvariable=self.map_search_var, placeholder_text="Cutoff, Send...", width=130)
        self.map_search_entry.pack(side="left", padx=4, pady=8)
        self.map_search_entry.bind("<KeyRelease>", lambda e: self._on_map_filter_changed())
        
        # Compteur
        self.lbl_map_count = ctk.CTkLabel(map_filter_bar, text="0 mapping(s)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
        self.lbl_map_count.pack(side="right", padx=15, pady=8)

        # 2. Barre d'Actions Groupées
        map_batch_bar = ctk.CTkFrame(self.tab_mappings, fg_color="#1c1c22", corner_radius=6)
        map_batch_bar.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 8))
        
        ctk.CTkLabel(map_batch_bar, text="Décaler Canaux MIDI :", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(10, 5), pady=5)
        btn_ch_minus = ctk.CTkButton(map_batch_bar, text="Canal -1", width=70, height=26, font=ctk.CTkFont(size=11), command=lambda: self._batch_shift_mapping_channel(-1))
        btn_ch_minus.pack(side="left", padx=2, pady=5)
        btn_ch_plus = ctk.CTkButton(map_batch_bar, text="Canal +1", width=70, height=26, font=ctk.CTkFont(size=11), command=lambda: self._batch_shift_mapping_channel(1))
        btn_ch_plus.pack(side="left", padx=2, pady=5)
        
        ctk.CTkLabel(map_batch_bar, text="Décaler CC :", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(20, 5), pady=5)
        btn_cc_minus = ctk.CTkButton(map_batch_bar, text="CC -1", width=60, height=26, font=ctk.CTkFont(size=11), command=lambda: self._batch_shift_mapping_cc(-1))
        btn_cc_minus.pack(side="left", padx=2, pady=5)
        btn_cc_plus = ctk.CTkButton(map_batch_bar, text="CC +1", width=60, height=26, font=ctk.CTkFont(size=11), command=lambda: self._batch_shift_mapping_cc(1))
        btn_cc_plus.pack(side="left", padx=2, pady=5)

        # 3. Grille Déroulante
        self.mappings_scroll = ctk.CTkScrollableFrame(self.tab_mappings, label_text="Tableau des Assignations avec Contrôleurs Identifiés", label_font=ctk.CTkFont(weight="bold"))
        self.mappings_scroll.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self.mappings_scroll.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8), weight=1)
        
        self.mapping_row_widgets = []
        self._render_mapping_headers()

    def _render_mapping_headers(self):
        headers = ["ID", "Paramètre Lié (Piste | Appareil | Param)", "Matériel / Contrôleur", "Type", "Canal MIDI", "Note / CC", "Min", "Max", "Actions"]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.mappings_scroll, text=text, font=ctk.CTkFont(weight="bold", size=12))
            lbl.grid(row=0, column=col, padx=4, pady=8)

    # ==================== GESTION DE LA BOÎTE DE DIALOGUE HARDWARE ====================
    def _open_hardware_naming_dialog(self):
        groups = self.editor.get_channel_groups()
        if not groups:
            messagebox.showinfo("Information", "Veuillez d'abord charger un projet Ableton (.als) contenant des mappings.")
            return
            
        def on_save(new_aliases):
            for ch, name in new_aliases.items():
                self.editor.set_hardware_alias(ch, name)
            self._update_all_filter_menus()
            self._refresh_mappings_view()
            
        HardwareNamingDialog(self, self.editor, groups, on_save)

    def _open_hardware_report_dialog(self):
        groups = self.editor.get_channel_groups()
        if not groups:
            messagebox.showinfo("Information", "Veuillez d'abord charger un projet Ableton (.als) contenant des mappings.")
            return
            
        def on_apply(suggestions):
            for ch, name in suggestions.items():
                self.editor.set_hardware_alias(ch, name)
            self._update_all_filter_menus()
            self._refresh_mappings_view()
            
        HardwareReportDialog(self, self.editor, on_apply)

    # ==================== CONFIGURATION ONGLET NOTES ====================
    def _setup_notes_tab(self):
        self.tab_notes.grid_columnconfigure(0, weight=1)
        self.tab_notes.grid_rowconfigure(2, weight=1)
        
        filter_bar = ctk.CTkFrame(self.tab_notes, fg_color="#24242c", corner_radius=6)
        filter_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 8))
        
        ctk.CTkLabel(filter_bar, text="Piste :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 5), pady=8)
        self.note_track_menu = ctk.CTkOptionMenu(filter_bar, values=["Toutes les pistes"], command=self._on_note_track_filter_changed, width=160)
        self.note_track_menu.pack(side="left", padx=5, pady=8)
        
        ctk.CTkLabel(filter_bar, text="Clip :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(15, 5), pady=8)
        self.note_clip_menu = ctk.CTkOptionMenu(filter_bar, values=["Tous les clips"], command=self._on_note_clip_filter_changed, width=160)
        self.note_clip_menu.pack(side="left", padx=5, pady=8)
        
        self.btn_next_page = ctk.CTkButton(filter_bar, text="▶", width=36, command=self._next_notes_page)
        self.btn_next_page.pack(side="right", padx=(5, 10), pady=8)
        
        self.lbl_notes_page_info = ctk.CTkLabel(filter_bar, text="Page 0 / 0 (0 notes)", font=ctk.CTkFont(size=12))
        self.lbl_notes_page_info.pack(side="right", padx=10, pady=8)
        
        self.btn_prev_page = ctk.CTkButton(filter_bar, text="◀", width=36, command=self._prev_notes_page)
        self.btn_prev_page.pack(side="right", padx=5, pady=8)

        # Actions Groupées Notes
        batch_bar = ctk.CTkFrame(self.tab_notes, fg_color="#1c1c22", corner_radius=6)
        batch_bar.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 8))
        
        ctk.CTkLabel(batch_bar, text="Transposer :", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(10, 4), pady=5)
        for semi, txt in [(-12, "-1 Oct"), (-1, "-1 Demi"), (1, "+1 Demi"), (12, "+1 Oct")]:
            btn = ctk.CTkButton(batch_bar, text=txt, width=65, height=26, font=ctk.CTkFont(size=11), command=lambda s=semi: self._batch_transpose(s))
            btn.pack(side="left", padx=2, pady=5)
            
        ctk.CTkLabel(batch_bar, text="Vélocité :", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(15, 4), pady=5)
        for delta, txt in [(-10, "-10"), (10, "+10")]:
            btn = ctk.CTkButton(batch_bar, text=txt, width=45, height=26, font=ctk.CTkFont(size=11), command=lambda d=delta: self._batch_velocity_delta(d))
            btn.pack(side="left", padx=2, pady=5)
        btn_v100 = ctk.CTkButton(batch_bar, text="Fixe 100", width=60, height=26, font=ctk.CTkFont(size=11), command=lambda: self._batch_velocity_fixed(100))
        btn_v100.pack(side="left", padx=2, pady=5)
        btn_v127 = ctk.CTkButton(batch_bar, text="Max 127", width=60, height=26, font=ctk.CTkFont(size=11), command=lambda: self._batch_velocity_fixed(127))
        btn_v127.pack(side="left", padx=2, pady=5)
        
        btn_mute_all = ctk.CTkButton(batch_bar, text="Mute Tout", width=70, height=26, font=ctk.CTkFont(size=11), fg_color="#6c757d", hover_color="#5a6268", command=lambda: self._batch_mute(False))
        btn_mute_all.pack(side="right", padx=(2, 10), pady=5)
        btn_unmute_all = ctk.CTkButton(batch_bar, text="Activer Tout", width=75, height=26, font=ctk.CTkFont(size=11), fg_color="#007bff", hover_color="#0069d9", command=lambda: self._batch_mute(True))
        btn_unmute_all.pack(side="right", padx=2, pady=5)

        self.notes_scroll = ctk.CTkScrollableFrame(self.tab_notes, label_text="Liste des Événements MIDI Détectés", label_font=ctk.CTkFont(weight="bold"))
        self.notes_scroll.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self.notes_scroll.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6, 7), weight=1)
        
        self.note_row_widgets = []
        self._render_notes_headers()

    def _render_notes_headers(self):
        headers = ["Piste", "Clip", "Note (ex: C3)", "Début (Beats)", "Durée (Beats)", "Vélocité", "Actif", "Action"]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.notes_scroll, text=text, font=ctk.CTkFont(weight="bold", size=12))
            lbl.grid(row=0, column=col, padx=4, pady=6)

    # ==================== CHARGEMENT DE PROJET ====================
    def load_project(self):
        file_path = filedialog.askopenfilename(filetypes=[("Projet Ableton", "*.als")])
        if file_path:
            try:
                self.editor.load_project(file_path)
                summary = self.editor.get_summary()
                
                self.status_label.configure(
                    text=f"Projet actif : {os.path.basename(file_path)}  •  {summary['creator']}",
                    font=ctk.CTkFont(size=13, weight="bold")
                )
                
                self.stats_lbl_maps.configure(text=f"🎛️ Mappings Contrôleurs : {summary['mappings']}")
                self.stats_lbl_tracks.configure(text=f"🎵 Pistes MIDI : {summary['midi_tracks']} / {summary['tracks']}")
                self.stats_lbl_clips.configure(text=f"🎼 Clips MIDI : {summary['clips']}")
                self.stats_lbl_notes.configure(text=f"🎹 Notes MIDI : {summary['notes']}")
                
                self.export_btn.configure(state="normal")
                self.export_json_btn.configure(state="normal")
                self.save_tpl_btn.configure(state="normal")
                self.load_tpl_btn.configure(state="normal")
                
                self._update_all_filter_menus()
                
                self._refresh_mappings_view()
                self.notes_page = 0
                self._filter_and_refresh_notes()
                
                self.tabview.set("🎛️ Mappings Contrôleurs (Ctrl+M)")
                
            except Exception as e:
                messagebox.showerror("Erreur de Lecture", f"Impossible de charger le projet .als:\n{str(e)}")

    def _update_all_filter_menus(self):
        # Mettre à jour menu Piste pour les Mappings
        mappings = self.editor.get_mappings()
        map_tracks = sorted(list(set(m['track'] for m in mappings if m.get('track'))))
        self.map_track_menu.configure(values=["Toutes les pistes"] + map_tracks)
        self.map_track_menu.set("Toutes les pistes")
        
        # Mettre à jour menu Matériels
        hw_names = sorted(list(set(m['hardware_name'] for m in mappings if m.get('hardware_name'))))
        self.map_hw_menu.configure(values=["Tous les matériels"] + hw_names)
        self.map_hw_menu.set("Tous les matériels")
        
        # Mettre à jour menu Pistes pour les Notes
        tracks = self.editor.get_tracks()
        midi_tracks = [t for t in tracks if t['is_midi']]
        track_names = ["Toutes les pistes"] + [f"{t['index']}: {t['name']}" for t in midi_tracks]
        self.note_track_menu.configure(values=track_names)
        self.note_track_menu.set("Toutes les pistes")
        self._update_note_clips_menu(track_idx=None)

    # ==================== LOGIQUE AFFICHAGE & ÉDITION MAPPINGS ====================
    def _on_map_filter_changed(self, *args):
        self._refresh_mappings_view()

    def _refresh_mappings_view(self):
        for widgets in self.mapping_row_widgets:
            for w in widgets:
                w.destroy()
        self.mapping_row_widgets.clear()
        
        selected_hw = self.map_hw_menu.get()
        selected_track = self.map_track_menu.get()
        selected_type = self.map_type_menu.get()
        search_query = self.map_search_var.get().strip().lower()
        
        mappings = self.editor.get_mappings()
        filtered = []
        for m in mappings:
            if selected_hw != "Tous les matériels" and m['hardware_name'] != selected_hw:
                continue
            if selected_track != "Toutes les pistes" and m['track'] != selected_track:
                continue
            if selected_type != "Tous" and m['type'] != selected_type:
                continue
            if search_query:
                target_str = m['target_desc'].lower()
                hw_str = m['hardware_name'].lower()
                if search_query not in target_str and search_query not in m['cc'] and search_query not in hw_str:
                    continue
            filtered.append(m)
            
        self.current_mappings = filtered
        self.lbl_map_count.configure(text=f"{len(filtered)} mapping(s) affiché(s) sur {len(mappings)}")
        
        if not filtered:
            msg = "Aucun mapping ne correspond aux critères de filtre." if mappings else "Aucun mapping de contrôleur physique trouvé dans ce projet."
            info_lbl = ctk.CTkLabel(self.mappings_scroll, text=msg, text_color="gray60")
            info_lbl.grid(row=1, column=0, columnspan=9, pady=30)
            self.mapping_row_widgets.append([info_lbl])
            return

        for i, m in enumerate(filtered, start=1):
            id_lbl = ctk.CTkLabel(self.mappings_scroll, text=m['id'], width=45)
            id_lbl.grid(row=i, column=0, padx=4, pady=5)
            
            target_lbl = ctk.CTkLabel(self.mappings_scroll, text=m['target_desc'], anchor="w")
            target_lbl.grid(row=i, column=1, padx=4, pady=5, sticky="w")
            
            # Badge Matériel / Contrôleur
            hw_badge = ctk.CTkLabel(
                self.mappings_scroll, 
                text=f"🎛️ {m['hardware_name']}", 
                fg_color="#1e293b", 
                corner_radius=4,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#38bdf8",
                padx=6,
                pady=2
            )
            hw_badge.grid(row=i, column=2, padx=4, pady=5)
            
            type_lbl = ctk.CTkLabel(self.mappings_scroll, text=m['type'], width=40)
            type_lbl.grid(row=i, column=3, padx=4, pady=5)
            
            ch_var = ctk.StringVar(value=m['channel'])
            ch_entry = ctk.CTkEntry(self.mappings_scroll, textvariable=ch_var, width=45)
            ch_entry.grid(row=i, column=4, padx=4, pady=5)
            
            cc_var = ctk.StringVar(value=m['cc'])
            cc_entry = ctk.CTkEntry(self.mappings_scroll, textvariable=cc_var, width=45)
            cc_entry.grid(row=i, column=5, padx=4, pady=5)
            
            min_var = ctk.StringVar(value=m.get('min', 'N/A'))
            min_entry = ctk.CTkEntry(self.mappings_scroll, textvariable=min_var, width=65)
            if m.get('min', 'N/A') == 'N/A':
                min_entry.configure(state="disabled")
            min_entry.grid(row=i, column=6, padx=4, pady=5)
            
            max_var = ctk.StringVar(value=m.get('max', 'N/A'))
            max_entry = ctk.CTkEntry(self.mappings_scroll, textvariable=max_var, width=65)
            if m.get('max', 'N/A') == 'N/A':
                max_entry.configure(state="disabled")
            max_entry.grid(row=i, column=7, padx=4, pady=5)
            
            action_frame = ctk.CTkFrame(self.mappings_scroll, fg_color="transparent")
            action_frame.grid(row=i, column=8, padx=4, pady=5)
            
            save_btn = ctk.CTkButton(
                action_frame, text="✓", width=34, height=28,
                command=lambda m_item=m, ch=ch_var, cc=cc_var, mn=min_var, mx=max_var: self._save_single_mapping(m_item, ch.get(), cc.get(), mn.get(), mx.get())
            )
            save_btn.pack(side="left", padx=2)
            
            del_btn = ctk.CTkButton(
                action_frame, text="🗑️", width=34, height=28, fg_color="#dc3545", hover_color="#c82333",
                command=lambda m_item=m: self._delete_single_mapping(m_item)
            )
            del_btn.pack(side="left", padx=2)
            
            self.mapping_row_widgets.append((id_lbl, target_lbl, hw_badge, type_lbl, ch_entry, cc_entry, min_entry, max_entry, action_frame))

    def _save_single_mapping(self, mapping_item, new_ch, new_cc, new_min, new_max):
        try:
            if self.editor.update_mapping(mapping_item, new_ch, new_cc, new_min, new_max):
                self._update_all_filter_menus()
                self._refresh_mappings_view()
            else:
                messagebox.showerror("Erreur", "Impossible de mettre à jour le mapping.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur de modification:\n{str(e)}")

    def _delete_single_mapping(self, mapping_item):
        if self.editor.delete_mapping(mapping_item):
            summary = self.editor.get_summary()
            self.stats_lbl_maps.configure(text=f"🎛️ Mappings Contrôleurs : {summary['mappings']}")
            self._update_all_filter_menus()
            self._refresh_mappings_view()

    def _batch_shift_mapping_channel(self, delta):
        if not self.current_mappings:
            return
        for m in self.current_mappings:
            try:
                curr_ch = int(m['channel'])
                new_ch = max(1, min(16, curr_ch + delta))
                self.editor.update_mapping(m, new_channel=new_ch, new_cc=m['cc'])
            except ValueError:
                pass
        self._update_all_filter_menus()
        self._refresh_mappings_view()

    def _batch_shift_mapping_cc(self, delta):
        if not self.current_mappings:
            return
        for m in self.current_mappings:
            try:
                curr_cc = int(m['cc'])
                new_cc = max(0, min(127, curr_cc + delta))
                self.editor.update_mapping(m, new_channel=m['channel'], new_cc=new_cc)
            except ValueError:
                pass
        self._update_all_filter_menus()
        self._refresh_mappings_view()

    # ==================== LOGIQUE AFFICHAGE & ÉDITION NOTES ====================
    def _update_note_clips_menu(self, track_idx=None):
        clips = self.editor.get_clips(track_idx=track_idx)
        clip_names = ["Tous les clips"] + [f"{c['clip_id']}: {c['clip_name']} ({c['notes_count']} notes)" for c in clips]
        self.note_clip_menu.configure(values=clip_names)
        self.note_clip_menu.set("Tous les clips")

    def _on_note_track_filter_changed(self, choice):
        track_idx = None
        if choice != "Toutes les pistes":
            try:
                track_idx = int(choice.split(":")[0])
            except ValueError:
                pass
        self._update_note_clips_menu(track_idx=track_idx)
        self.notes_page = 0
        self._filter_and_refresh_notes()

    def _on_note_clip_filter_changed(self, choice):
        self.notes_page = 0
        self._filter_and_refresh_notes()

    def _get_note_filters(self):
        track_choice = self.note_track_menu.get()
        clip_choice = self.note_clip_menu.get()
        track_idx = None
        if track_choice != "Toutes les pistes":
            try:
                track_idx = int(track_choice.split(":")[0])
            except ValueError:
                pass
        clip_id = None
        if clip_choice != "Tous les clips":
            try:
                clip_id = clip_choice.split(":")[0]
            except ValueError:
                pass
        return track_idx, clip_id

    def _filter_and_refresh_notes(self):
        track_idx, clip_id = self._get_note_filters()
        self.current_notes = self.editor.get_midi_notes(track_idx=track_idx, clip_id=clip_id)
        self._render_current_notes_page()

    def _render_current_notes_page(self):
        for widgets in self.note_row_widgets:
            for w in widgets:
                w.destroy()
        self.note_row_widgets.clear()
        
        total_notes = len(self.current_notes)
        if total_notes == 0:
            self.lbl_notes_page_info.configure(text="Page 0 / 0 (0 notes)")
            lbl = ctk.CTkLabel(self.notes_scroll, text="Aucun événement de note MIDI trouvé pour ce filtre.", text_color="gray60")
            lbl.grid(row=1, column=0, columnspan=8, pady=30)
            self.note_row_widgets.append([lbl])
            return
            
        total_pages = max(1, (total_notes + self.notes_page_size - 1) // self.notes_page_size)
        self.notes_page = min(self.notes_page, total_pages - 1)
        start_idx = self.notes_page * self.notes_page_size
        end_idx = min(start_idx + self.notes_page_size, total_notes)
        
        self.lbl_notes_page_info.configure(text=f"Page {self.notes_page + 1} / {total_pages} ({total_notes} notes)")
        page_notes = self.current_notes[start_idx:end_idx]
        
        for i, note in enumerate(page_notes, start=1):
            t_lbl = ctk.CTkLabel(self.notes_scroll, text=note['track_name'], width=100)
            t_lbl.grid(row=i, column=0, padx=4, pady=3)
            
            c_lbl = ctk.CTkLabel(self.notes_scroll, text=note['clip_name'], width=100)
            c_lbl.grid(row=i, column=1, padx=4, pady=3)
            
            note_var = ctk.StringVar(value=f"{note['note_name']} ({note['pitch']})")
            note_entry = ctk.CTkEntry(self.notes_scroll, textvariable=note_var, width=80)
            note_entry.grid(row=i, column=2, padx=4, pady=3)
            
            time_var = ctk.StringVar(value=str(note['time']))
            time_entry = ctk.CTkEntry(self.notes_scroll, textvariable=time_var, width=80)
            time_entry.grid(row=i, column=3, padx=4, pady=3)
            
            dur_var = ctk.StringVar(value=str(note['duration']))
            dur_entry = ctk.CTkEntry(self.notes_scroll, textvariable=dur_var, width=80)
            dur_entry.grid(row=i, column=4, padx=4, pady=3)
            
            vel_var = ctk.StringVar(value=str(int(note['velocity'])))
            vel_entry = ctk.CTkEntry(self.notes_scroll, textvariable=vel_var, width=60)
            vel_entry.grid(row=i, column=5, padx=4, pady=3)
            
            en_var = ctk.BooleanVar(value=note['is_enabled'])
            en_cb = ctk.CTkCheckBox(self.notes_scroll, text="", variable=en_var, width=30)
            en_cb.grid(row=i, column=6, padx=4, pady=3)
            
            action_frame = ctk.CTkFrame(self.notes_scroll, fg_color="transparent")
            action_frame.grid(row=i, column=7, padx=4, pady=3)
            
            save_btn = ctk.CTkButton(
                action_frame, text="✓", width=36, height=28,
                command=lambda n=note, nv=note_var, tv=time_var, dv=dur_var, vv=vel_var, ev=en_var: self._save_single_note(n, nv.get(), tv.get(), dv.get(), vv.get(), ev.get())
            )
            save_btn.pack(side="left", padx=2)
            
            del_btn = ctk.CTkButton(
                action_frame, text="🗑️", width=36, height=28, fg_color="#dc3545", hover_color="#c82333",
                command=lambda n=note: self._delete_single_note(n)
            )
            del_btn.pack(side="left", padx=2)
            
            self.note_row_widgets.append((t_lbl, c_lbl, note_entry, time_entry, dur_entry, vel_entry, en_cb, action_frame))

    def _save_single_note(self, note_item, raw_pitch, raw_time, raw_dur, raw_vel, is_en):
        parsed_pitch = raw_pitch.split("(")[0].strip() if "(" in raw_pitch else raw_pitch
        success = self.editor.update_midi_note(
            note_item,
            new_pitch=parsed_pitch,
            new_time=raw_time,
            new_duration=raw_dur,
            new_velocity=raw_vel,
            new_enabled=is_en
        )
        if success:
            self._render_current_notes_page()

    def _delete_single_note(self, note_item):
        if self.editor.delete_midi_note(note_item):
            if note_item in self.current_notes:
                self.current_notes.remove(note_item)
            self._render_current_notes_page()
            summary = self.editor.get_summary()
            self.stats_lbl_notes.configure(text=f"🎹 Notes MIDI : {summary['notes']}")

    def _prev_notes_page(self):
        if self.notes_page > 0:
            self.notes_page -= 1
            self._render_current_notes_page()

    def _next_notes_page(self):
        total_pages = max(1, (len(self.current_notes) + self.notes_page_size - 1) // self.notes_page_size)
        if self.notes_page < total_pages - 1:
            self.notes_page += 1
            self._render_current_notes_page()

    def _batch_transpose(self, semitones):
        if not self.current_notes: return
        self.editor.batch_transpose(self.current_notes, semitones)
        self._render_current_notes_page()

    def _batch_velocity_delta(self, delta):
        if not self.current_notes: return
        self.editor.batch_velocity(self.current_notes, delta=delta)
        self._render_current_notes_page()

    def _batch_velocity_fixed(self, fixed_val):
        if not self.current_notes: return
        self.editor.batch_velocity(self.current_notes, fixed_val=fixed_val)
        self._render_current_notes_page()

    def _batch_mute(self, is_enabled):
        if not self.current_notes: return
        self.editor.batch_set_active(self.current_notes, is_enabled)
        self._render_current_notes_page()

    # ==================== EXPORT & TEMPLATES ====================
    def export_project(self):
        if not self.editor.root:
            return
        orig_name = os.path.basename(self.editor.file_path) if self.editor.file_path else "Projet.als"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".als", 
            filetypes=[("Projet Ableton Live", "*.als")],
            initialfile=f"Export_{orig_name}"
        )
        if file_path:
            try:
                self.editor.export_project(file_path)
                messagebox.showinfo("Exportation Réussie", f"Fichier .als régénéré avec succès :\n{file_path}\n\nLe projet original est intact et inchangé.")
            except Exception as e:
                messagebox.showerror("Erreur d'Écriture", f"Impossible d'exporter le fichier .als:\n{str(e)}")

    def export_notes_json(self):
        if not self.editor.root:
            return
        track_idx, clip_id = self._get_note_filters()
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Notes Export", "*.json")], initialfile="midi_notes_export.json")
        if file_path:
            try:
                self.editor.export_notes_to_json(file_path, track_idx=track_idx, clip_id=clip_id)
                messagebox.showinfo("Succès", f"Notes MIDI exportées avec succès vers :\n{file_path}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Échec de l'export JSON:\n{str(e)}")

    def save_template(self):
        if not self.editor.root:
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Profil Mappings JSON", "*.json")], initialfile="profil_mappings.json")
        if file_path:
            try:
                self.editor.save_template(file_path)
                messagebox.showinfo("Profil Sauvegardé", "Les mappings et les noms de contrôleurs ont été sauvegardés sous forme de profil.")
            except Exception as e:
                messagebox.showerror("Erreur", f"Échec de la sauvegarde:\n{str(e)}")

    def load_template(self):
        if not self.editor.root:
            return
        file_path = filedialog.askopenfilename(filetypes=[("Profil Mappings JSON", "*.json")])
        if file_path:
            try:
                applied = self.editor.load_template(file_path)
                self._update_all_filter_menus()
                self._refresh_mappings_view()
                messagebox.showinfo("Profil Appliqué", f"{applied} mapping(s) ont été réassignés avec succès.")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'appliquer le profil:\n{str(e)}")

if __name__ == "__main__":
    app = AbletonMidiApp()
    app.mainloop()
