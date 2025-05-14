import sys

def resource_path(relative_path):
    """ Pfad zu Ressourcen (für PyInstaller-kompatible Nutzung) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import json
from datetime import datetime, timedelta
import pytz
import requests
from bs4 import BeautifulSoup

from sos_parser import SosParser
from eigene_truppen_parser import EigeneTruppenParser
from tab_matching import TabMatching

class StammGUI:
    if getattr(sys, 'frozen', False):
        # Wenn gebundene .exe (PyInstaller)
        ANWENDER_PFAD = os.path.dirname(sys.executable)
    else:
        # Wenn als .py ausgeführt
        ANWENDER_PFAD = os.path.dirname(os.path.abspath(__file__))

    VERLAUF_DATEI = os.path.join(ANWENDER_PFAD, "tabverlauf.json")

    def __init__(self, root):
        self.tk_root = root
        self.tk_root.title("Die Stämme SOS Tool")

        self.matches = []
        self.tabgroessen_liste = []
        self.export_button = None
        self.welt_speed = 1.0
        self.einheiten_speed = 1.0
        self.welt_id = ""
        self.boost_level = 0

        self.build_gui()
        self.lade_tabverlauf()

    def build_gui(self):
        self.text_fields = {}
        labels = ["SOS Anfrage", "Eigene Truppen", "Unterstützungen"]
        for idx, label in enumerate(labels):
            ttk.Label(self.tk_root, text=label + ":").grid(row=idx, column=0, sticky="nw", padx=5, pady=(2, 2))
            text = tk.Text(self.tk_root, width=60, height=3)
            text.grid(row=idx, column=1, padx=5, pady=(2, 2))
            self.text_fields[label] = text

        ttk.Label(self.tk_root, text="Welt-ID (z.B. 236):").grid(row=0, column=2, sticky="nw", padx=5, pady=(2, 2))
        self.welt_id_entry = ttk.Entry(self.tk_root, width=5)
        self.welt_id_entry.grid(row=0, column=3, sticky="nw", padx=5, pady=(2, 2))

        ttk.Label(self.tk_root, text="Level:").grid(row=1, column=2, sticky="nw", padx=5, pady=(2, 2))
        self.boost_entry = ttk.Entry(self.tk_root, width=5)
        self.boost_entry.insert(0, "0")
        self.boost_entry.grid(row=1, column=3, sticky="nw", padx=5, pady=(2, 2))

        self.einheiten = {
            "Speerträger": "unit_spear.webp",
            "Schwertkämpfer": "unit_sword.webp",
            "Axtkämpfer": "unit_axe.webp",
            "Späher": "unit_spy.webp",
            "Leichte Kavallerie": "unit_light.webp",
            "Schwere Kavallerie": "unit_heavy.webp",
            "Rammböcke": "unit_ram.webp",
            "Katapulte": "unit_catapult.webp"
        }

        self.checkbox_vars = {}
        self.entry_fields = {}
        self.image_refs = {}
        self.tab_config_display = None

        unit_frame = ttk.LabelFrame(self.tk_root, text="Einheiten Auswahl")
        unit_frame.grid(row=3, column=0, columnspan=4, padx=10, pady=10, sticky="ew")

        for idx, (name, img_file) in enumerate(self.einheiten.items()):
            var = tk.BooleanVar()
            self.checkbox_vars[name] = var

            try:
                path = resource_path(os.path.join("images", img_file))
                img = Image.open(path).resize((30, 30))
                img_tk = ImageTk.PhotoImage(img)
                self.image_refs[name] = img_tk
            except Exception as e:
                print(f"Bildproblem bei {img_file}: {e}")
                continue

            row = idx // 4
            col = (idx % 4) * 2

            cb = tk.Checkbutton(unit_frame, text=name, variable=var, image=self.image_refs[name], compound="left")
            cb.grid(row=row, column=col, padx=5, pady=5, sticky="w")

            entry = ttk.Entry(unit_frame, width=5)
            entry.grid(row=row, column=col + 1, padx=5, pady=5, sticky="w")
            self.entry_fields[name] = entry

        ttk.Button(unit_frame, text="+ Kombination hinzufügen", command=self.tab_kombi_hinzufuegen).grid(row=3, column=0, columnspan=2, pady=10, sticky="w")
        self.tab_config_display = tk.Listbox(unit_frame, height=5, width=65)
        self.tab_config_display.grid(row=4, column=0, columnspan=4, sticky="ew", padx=5)

        button_frame = ttk.Frame(unit_frame)
        button_frame.grid(row=4, column=4, sticky="ne", padx=5)
        ttk.Button(button_frame, text="Tabkombination löschen", width=22, command=self.tab_kombi_loeschen).pack(side="top", pady=(0, 5))
        ttk.Button(button_frame, text="Verlauf löschen", width=22, command=self.verlauf_loeschen).pack(side="top")

        bottom_frame = ttk.LabelFrame(self.tk_root, text="Zeitfenster")
        bottom_frame.grid(row=4, column=0, columnspan=5, pady=20, padx=10, sticky="ew")

        ttk.Label(bottom_frame, text="Von:").grid(row=0, column=0, padx=(5, 2))
        self.from_entry = ttk.Entry(bottom_frame, width=20)
        self.from_entry.grid(row=0, column=1, padx=(0, 2))
        ttk.Button(bottom_frame, text="Wählen", command=lambda: self.datum_popup("Von", self.from_entry)).grid(row=0, column=2, padx=(0, 2))
        ttk.Button(bottom_frame, text="X", width=2, command=lambda: self.from_entry.delete(0, tk.END)).grid(row=0, column=3, padx=(0, 10))

        ttk.Label(bottom_frame, text="Bis:").grid(row=0, column=4, padx=(10, 2))
        self.to_entry = ttk.Entry(bottom_frame, width=20)
        self.to_entry.grid(row=0, column=5, padx=(0, 2))
        ttk.Button(bottom_frame, text="Wählen", command=lambda: self.datum_popup("Bis", self.to_entry)).grid(row=0, column=6, padx=(0, 2))
        ttk.Button(bottom_frame, text="X", width=2, command=lambda: self.to_entry.delete(0, tk.END)).grid(row=0, column=7, padx=(0, 10))

        ttk.Button(bottom_frame, text="Berechne Tabs", command=self.berechne_tabs).grid(row=0, column=8, padx=(20, 10), ipadx=40, ipady=10, sticky="e")

    def tab_kombi_hinzufuegen(self):
        kombi = {}
        beschreibung = []
        for name, entry in self.entry_fields.items():
            if self.checkbox_vars[name].get():
                try:
                    menge = int(entry.get())
                    if menge > 0:
                        kombi[name] = menge
                        beschreibung.append(f"{menge}x {name}")
                except ValueError:
                    continue
        if kombi:
            self.tabgroessen_liste.append(kombi)
            self.tab_config_display.insert(tk.END, ", ".join(beschreibung))
            self.speichere_tabverlauf()

    def tab_kombi_loeschen(self):
        auswahl = self.tab_config_display.curselection()
        for index in reversed(auswahl):
            self.tab_config_display.delete(index)
            del self.tabgroessen_liste[index]
            self.speichere_tabverlauf()

    def lade_tabverlauf(self):
        try:
            if os.path.exists(self.VERLAUF_DATEI):
                with open(self.VERLAUF_DATEI, "r", encoding="utf-8") as f:
                    daten = json.load(f)
                    for kombi in daten:
                        self.tabgroessen_liste.append(kombi)
                        beschreibung = [f"{menge}x {einheit}" for einheit, menge in kombi.items()]
                        self.tab_config_display.insert(tk.END, ", ".join(beschreibung))
        except Exception as e:
            print(f"Fehler beim Laden des Verlaufs: {e}")

    def speichere_tabverlauf(self):
        try:
            with open(self.VERLAUF_DATEI, "w", encoding="utf-8") as f:
                json.dump(self.tabgroessen_liste, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern des Verlaufs: {e}")

    def verlauf_loeschen(self):
        if os.path.exists(self.VERLAUF_DATEI):
            os.remove(self.VERLAUF_DATEI)
        self.tab_config_display.delete(0, tk.END)
        self.tabgroessen_liste.clear()

    def berechne_tabs(self):
        try:
            welt_id = self.welt_id_entry.get().strip()
            if not welt_id.isdigit():
                print("Ungültige Welt-ID")
                return

            self.welt_id = welt_id
            self.lade_geschwindigkeiten(welt_id)

            sos_text = self.text_fields["SOS Anfrage"].get("1.0", "end").strip()
            truppen_text = self.text_fields["Eigene Truppen"].get("1.0", "end").strip()

            angriffe = SosParser.parse(sos_text)
            eigene_dörfer = EigeneTruppenParser.parse(truppen_text)

            zeitfenster_von = self.from_entry.get().strip()
            zeitfenster_bis = self.to_entry.get().strip()

            von_dt = datetime.strptime(zeitfenster_von, "%d.%m.%Y %H:%M:%S") if zeitfenster_von else None
            bis_dt = datetime.strptime(zeitfenster_bis, "%d.%m.%Y %H:%M:%S") if zeitfenster_bis else None

            if von_dt and bis_dt and bis_dt < von_dt:
                messagebox.showerror("Zeitfenster Fehler", "Das 'Bis'-Datum darf nicht vor dem 'Von'-Datum liegen.")
                return

            von_dt = pytz.timezone("Europe/Berlin").localize(von_dt) if von_dt else None
            bis_dt = pytz.timezone("Europe/Berlin").localize(bis_dt) if bis_dt else None

            try:
                self.boost_level = int(self.boost_entry.get().strip())
            except ValueError:
                self.boost_level = 0

            self.matches = TabMatching.finde_tabs(
                angriffe=angriffe,
                eigene_dörfer=eigene_dörfer,
                tabgroessen_liste=self.tabgroessen_liste,
                welt_speed=self.welt_speed,
                einheiten_speed=self.einheiten_speed,
                zeitfenster_von=von_dt,
                zeitfenster_bis=bis_dt,
                boost_level=self.boost_level  
            )

            print(f"{len(self.matches)} Tabs gefunden und bereit zum Export")

            if self.export_button:
                self.export_button.destroy()
            self.export_button = ttk.Button(self.tk_root, text="Exportieren", command=self.exportiere)
            self.export_button.grid(row=5, column=0, columnspan=4, pady=10)

        except Exception as e:
            print(f"Fehler bei der Tabberechnung: {e}")


    def lade_geschwindigkeiten(self, welt_id):
        url = f"https://de{welt_id}.die-staemme.de/page/settings"
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

            welt_row = soup.find("td", string="Spielgeschwindigkeit")
            einheit_row = soup.find("td", string="Einheitengeschwindigkeit")

            if not welt_row or not einheit_row:
                raise ValueError("Konnte Geschwindigkeitsdaten nicht finden.")

            welt_speed = welt_row.find_next_sibling("td").text.strip()
            einheit_speed = einheit_row.find_next_sibling("td").text.strip()

            print(f"[INFO] Weltgeschwindigkeit: {welt_speed}, Einheitengeschwindigkeit: {einheit_speed}")

            self.welt_speed = float(welt_speed)
            self.einheiten_speed = float(einheit_speed)
        except Exception as e:
            print(f"Fehler beim Laden der Geschwindigkeiten: {e}")


    def datum_popup(self, title, entry_widget):
        popup = tk.Toplevel(self.tk_root)
        popup.title(title)
        popup.geometry("280x250")
        popup.resizable(False, False)

        is_bis = "bis" in title.lower()
        default_time = datetime.now() + timedelta(hours=1) if is_bis else datetime.now()

        def übernehmen():
            try:
                dt = datetime(
                    int(year.get()), int(month.get()), int(day.get()),
                    int(hour.get()), int(minute.get()), int(second.get())
                )
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, dt.strftime("%d.%m.%Y %H:%M:%S"))
                popup.destroy()
            except:
                print("Datum ungültig")

        def jetzt():
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
            popup.destroy()

        def plus_min():
            try:
                minuten = int(plus.get())
                dt = datetime.now() + timedelta(minutes=minuten)
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, dt.strftime("%d.%m.%Y %H:%M:%S"))
                popup.destroy()
            except:
                print("Minuten ungültig")

        container = ttk.Frame(popup)
        container.pack(expand=True)

        ttk.Label(container, text="Datum & Uhrzeit wählen", font=("Segoe UI", 10, "bold")).pack(pady=(10, 10))

        grid = ttk.Frame(container)
        grid.pack()

        year = ttk.Combobox(grid, values=list(range(2024, 2031)), width=5)
        year.set(default_time.year)
        year.grid(row=0, column=0)

        month = ttk.Combobox(grid, values=list(range(1, 13)), width=3)
        month.set(default_time.month)
        month.grid(row=0, column=1)

        day = ttk.Combobox(grid, values=list(range(1, 32)), width=3)
        day.set(default_time.day)
        day.grid(row=0, column=2)

        hour = ttk.Combobox(grid, values=list(range(0, 24)), width=3)
        hour.set(default_time.hour)
        hour.grid(row=1, column=0)

        minute = ttk.Combobox(grid, values=list(range(0, 60)), width=3)
        minute.set(default_time.minute)
        minute.grid(row=1, column=1)

        second = ttk.Combobox(grid, values=list(range(0, 60)), width=3)
        second.set(default_time.second)
        second.grid(row=1, column=2)

        if not is_bis:
            ttk.Button(container, text="Jetzt", command=jetzt).pack(pady=(5, 0))

        plus_frame = ttk.Frame(container)
        plus_frame.pack(pady=(5, 5))
        plus = ttk.Entry(plus_frame, width=5)
        plus.insert(0, "60")
        plus.grid(row=0, column=0)
        ttk.Button(plus_frame, text="+ Min", command=plus_min).grid(row=0, column=1, padx=5)

        ttk.Button(container, text="Übernehmen", command=übernehmen).pack(pady=(5, 10))

    def exportiere(self):
        try:
            export_text = TabMatching.export_dsultimate(self.matches, self.welt_id_entry.get().strip())
            pfad = filedialog.asksaveasfilename(
                defaultextension=".txt", filetypes=[("Textdateien", "*.txt")], title="Speichern unter"
            )
            if pfad:
                with open(pfad, "w", encoding="utf-8") as f:
                    f.write(export_text)
                print(f"Export erfolgreich: {pfad}")
        except Exception as e:
            print(f"Export fehlgeschlagen: {e}")

# GUI starten
if __name__ == "__main__":
    root = tk.Tk()
    app = StammGUI(root)
    root.iconbitmap(resource_path("support.ico")) 
    root.mainloop()


