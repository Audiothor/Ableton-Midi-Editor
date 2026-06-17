import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from ableton_parser import AbletonMidiEditor

# Configuration de l'apparence selon les DAW (Thème Sombre)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AbletonMidiApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Éditeur de Configuration MIDI pour Ableton Live")
        self.geometry("1000x600")
        self.minsize(950, 500)
        
        self.editor = AbletonMidiEditor()
        
        # Configuration de la grille principale
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- Barre Latérale ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Ableton MIDI\nEditor", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        self.load_btn = ctk.CTkButton(self.sidebar, text="Importer Projet (.als)", command=self.load_project)
        self.load_btn.grid(row=1, column=0, padx=20, pady=10)
        
        self.save_tpl_btn = ctk.CTkButton(self.sidebar, text="Sauvegarder Template", command=self.save_template, state="disabled")
        self.save_tpl_btn.grid(row=2, column=0, padx=20, pady=10)
        
        self.load_tpl_btn = ctk.CTkButton(self.sidebar, text="Appliquer Template", command=self.load_template, state="disabled")
        self.load_tpl_btn.grid(row=3, column=0, padx=20, pady=10)
        
        self.export_btn = ctk.CTkButton(self.sidebar, text="Régénérer et Exporter", command=self.export_project, state="disabled", fg_color="#28a745", hover_color="#218838")
        self.export_btn.grid(row=4, column=0, padx=20, pady=(40, 10))
        
        # --- Zone Principale ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        self.status_label = ctk.CTkLabel(self.main_frame, text="Aucun projet chargé. Veuillez importer un fichier .als.", font=ctk.CTkFont(size=14, slant="italic"))
        self.status_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # Grille d'édition visuelle (Scrollable Frame)
        self.scrollable_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="Grille d'Édition Visuelle des Assignations", label_font=ctk.CTkFont(weight="bold"))
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.scrollable_frame.grid_columnconfigure((0,1,2,3,4,5,6), weight=1)
        
        # En-têtes du tableau
        headers = ["ID Mapping", "Paramètre Lié (ID)", "Canal MIDI", "Note / CC", "Min", "Max", "Action"]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.scrollable_frame, text=text, font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=0, column=col, padx=5, pady=10)
            
        self.mapping_rows = []

    def load_project(self):
        file_path = filedialog.askopenfilename(filetypes=[("Ableton Project", "*.als")])
        if file_path:
            try:
                self.editor.load_project(file_path)
                self.status_label.configure(text=f"Projet actif : {os.path.basename(file_path)}")
                self.refresh_grid()
                
                # Activer les boutons
                self.export_btn.configure(state="normal")
                self.save_tpl_btn.configure(state="normal")
                self.load_tpl_btn.configure(state="normal")
            except Exception as e:
                messagebox.showerror("Erreur de Lecture", f"Impossible de lire le fichier .als:\n{str(e)}")
                
    def refresh_grid(self):
        # Nettoyer la grille existante
        for row in self.mapping_rows:
            for widget in row:
                widget.destroy()
        self.mapping_rows.clear()
        
        mappings = self.editor.get_mappings()
        
        if not mappings:
            info_lbl = ctk.CTkLabel(self.scrollable_frame, text="Aucun mapping MIDI trouvé dans ce projet.")
            info_lbl.grid(row=1, column=0, columnspan=5, pady=20)
            self.mapping_rows.append([info_lbl])
            return

        for i, mapping in enumerate(mappings, start=1):
            id_lbl = ctk.CTkLabel(self.scrollable_frame, text=mapping['id'])
            id_lbl.grid(row=i, column=0, padx=5, pady=5)
            
            target_lbl = ctk.CTkLabel(self.scrollable_frame, text=mapping['target_id'])
            target_lbl.grid(row=i, column=1, padx=5, pady=5)
            
            ch_var = ctk.StringVar(value=mapping['channel'])
            ch_entry = ctk.CTkEntry(self.scrollable_frame, textvariable=ch_var, width=60)
            ch_entry.grid(row=i, column=2, padx=5, pady=5)
            
            cc_var = ctk.StringVar(value=mapping['cc'])
            cc_entry = ctk.CTkEntry(self.scrollable_frame, textvariable=cc_var, width=60)
            cc_entry.grid(row=i, column=3, padx=5, pady=5)
            
            min_var = ctk.StringVar(value=mapping.get('min', 'N/A'))
            min_entry = ctk.CTkEntry(self.scrollable_frame, textvariable=min_var, width=60)
            if mapping.get('min', 'N/A') == 'N/A':
                min_entry.configure(state="disabled")
            min_entry.grid(row=i, column=4, padx=5, pady=5)
            
            max_var = ctk.StringVar(value=mapping.get('max', 'N/A'))
            max_entry = ctk.CTkEntry(self.scrollable_frame, textvariable=max_var, width=60)
            if mapping.get('max', 'N/A') == 'N/A':
                max_entry.configure(state="disabled")
            max_entry.grid(row=i, column=5, padx=5, pady=5)
            
            update_btn = ctk.CTkButton(
                self.scrollable_frame, text="Appliquer", width=90,
                command=lambda m_id=mapping['id'], ch=ch_var, cc=cc_var, mn=min_var, mx=max_var: self.update_mapping(m_id, ch.get(), cc.get(), mn.get(), mx.get())
            )
            update_btn.grid(row=i, column=6, padx=5, pady=5)
            
            self.mapping_rows.append((id_lbl, target_lbl, ch_entry, cc_entry, min_entry, max_entry, update_btn))

    def update_mapping(self, mapping_id, new_channel, new_cc, new_min, new_max):
        try:
            if self.editor.update_mapping(mapping_id, new_channel, new_cc, new_min, new_max):
                pass # Feedback visuel optionnel : on pourrait changer la couleur du bouton
            else:
                messagebox.showerror("Erreur", f"Mapping {mapping_id} introuvable dans la structure XML.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la modification:\n{str(e)}")

    def export_project(self):
        if not self.editor.root:
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".als", 
            filetypes=[("Ableton Project", "*.als")],
            initialfile=f"Export_{os.path.basename(self.editor.file_path)}" if self.editor.file_path else "Export.als"
        )
        if file_path:
            try:
                self.editor.export_project(file_path)
                messagebox.showinfo("Succès", f"Fichier .als généré avec succès :\n{file_path}\n\nLe projet original n'a pas été altéré.")
            except Exception as e:
                messagebox.showerror("Erreur d'Écriture", f"Impossible de générer le fichier .als:\n{str(e)}")
                
    def save_template(self):
        if not self.editor.root:
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Profile", "*.json")])
        if file_path:
            try:
                self.editor.save_template(file_path)
                messagebox.showinfo("Profil Sauvegardé", "Les mappings actuels ont été sauvegardés en tant que Template.")
            except Exception as e:
                messagebox.showerror("Erreur", f"Échec de la sauvegarde du template:\n{str(e)}")
                
    def load_template(self):
        if not self.editor.root:
            return
        file_path = filedialog.askopenfilename(filetypes=[("JSON Profile", "*.json")])
        if file_path:
            try:
                self.editor.load_template(file_path)
                self.refresh_grid()
                messagebox.showinfo("Template Appliqué", "Le Template a été appliqué aux IDs correspondants.\n\nN'oubliez pas d'utiliser 'Régénérer et Exporter' pour sauvegarder les modifications sur un nouveau fichier projet.")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'appliquer le template:\n{str(e)}")

if __name__ == "__main__":
    app = AbletonMidiApp()
    app.mainloop()
