import base64
import copy
import gzip
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from tkinter import ttk
from typing import Dict, List

import pytz
import requests

from distanz_rechner import DistanzRechner
from einheiten import get_laufzeit


@dataclass
class TabMatch:
    herkunft: object
    ziel_koord: str
    abschickzeit: datetime
    ankunftszeit: datetime
    einheiten: Dict[str, int]
    einheit_kuerzel: str

class TabMatching:
    @staticmethod
    def finde_tabs(
        angriffe: List[object],
        eigene_dörfer: List[object],
        tabgroessen_liste: List[Dict[str, int]],
        welt_speed: float = 1.0,
        einheiten_speed: float = 1.0,
        zeitfenster_von: datetime = None,
        zeitfenster_bis: datetime = None,
        boost_level: int = 0
    ) -> List[TabMatch]:
        print(f"[INFO] {len(angriffe)} Angriffe, {len(eigene_dörfer)} eigene Dörfer verarbeitet")

        matches = []
        name_mapping = {
            "speerträger": "Speerträger",
            "schwertkämpfer": "Schwertkämpfer",
            "axtkämpfer": "Axtkämpfer",
            "späher": "Späher",
            "leichte kavallerie": "Leichte Kavallerie",
            "schwere kavallerie": "Schwere Kavallerie",
            "katapulte": "Katapulte"
        }

        laufzeit_einheiten = ["Axtkämpfer", "Späher", "Leichte Kavallerie", "Katapulte", "Schwertkämpfer"]
        tabrelevante_einheiten = ["Speerträger", "Schwertkämpfer", "Schwere Kavallerie"]

        dorf_copies = []
        for dorf in eigene_dörfer:
            dorf_copy = copy.deepcopy(dorf)
            dorf_copy.rest_truppen = copy.deepcopy(dorf.truppen)
            dorf_copies.append(dorf_copy)

        now = datetime.now(pytz.timezone("Europe/Berlin"))

        for angriff in angriffe:
            moegliche_tabs = []
            for dorf in dorf_copies:
                if dorf.koordinaten == angriff.ziel_koord:
                    continue

                distanz = DistanzRechner.berechne_distanz(dorf.koordinaten, angriff.ziel_koord)
                ankunftszeit = angriff.ankunftszeit
                if ankunftszeit.tzinfo is None:
                    ankunftszeit = pytz.timezone("Europe/Berlin").localize(ankunftszeit)

                for tabgroessen in tabgroessen_liste:
                    tab_einheiten = {
                        name_mapping[e.lower()]: menge for e, menge in tabgroessen.items()
                        if e.lower() in name_mapping and name_mapping[e.lower()] in tabrelevante_einheiten
                    }

                    kandidaten = [tab_einheiten.copy()]
                    for zusatz in laufzeit_einheiten:
                        if zusatz not in tab_einheiten and dorf.rest_truppen.get(zusatz, 0) > 0:
                            erweitert = tab_einheiten.copy()
                            erweitert[zusatz] = 1
                            kandidaten.append(erweitert)

                    for kandidat in kandidaten:
                        kandidat_mit_spaeh = kandidat.copy()
                        verfuegbare_spaeh = dorf.rest_truppen.get("Späher", 0)
                        if verfuegbare_spaeh >= 5:
                            kandidat_mit_spaeh["Späher"] = 5  # Add-on
                        elif verfuegbare_spaeh > 0:
                            kandidat_mit_spaeh["Späher"] = verfuegbare_spaeh  # So viele wie möglich

                        # Prüfen, ob die tabrelevanten Einheiten vorhanden sind (Späher NICHT relevant für Ausschluss)
                        if not all(dorf.rest_truppen.get(e, 0) >= m for e, m in kandidat.items()):
                            continue

                        if not kandidat:
                            continue

                        lz = max(get_laufzeit(e, welt_speed, einheiten_speed) for e in kandidat)
                        abschick = ankunftszeit - timedelta(minutes=distanz * lz)

                        # Zeitfensterprüfung
                        if abschick < now:
                            continue
                        if zeitfenster_von and abschick < zeitfenster_von:
                            continue
                        if zeitfenster_bis and abschick > zeitfenster_bis:
                            continue

                        tab = TabMatch(
                            herkunft=dorf,
                            ziel_koord=angriff.ziel_koord,
                            abschickzeit=abschick,
                            ankunftszeit=ankunftszeit,
                            einheiten=kandidat_mit_spaeh,
                            einheit_kuerzel=max(kandidat, key=lambda e: get_laufzeit(e, welt_speed, einheiten_speed))
                        )
                        moegliche_tabs.append((abschick, distanz, tab))

            if moegliche_tabs:
                moegliche_tabs.sort(key=lambda t: (t[0], t[1]))
                _, _, bester_match = moegliche_tabs[0]

                for einheit, menge in bester_match.einheiten.items():
                    bester_match.herkunft.rest_truppen[einheit] -= menge

                matches.append(bester_match)

        TabMatching.zeige_popup(len(angriffe), len(matches))
        return matches


    @staticmethod
    def zeige_popup(anz_angriffe: int, anz_tabs: int):
        popup = tk.Toplevel()
        popup.title("Tabberechnung abgeschlossen")
        popup.geometry("280x120")
        popup.resizable(False, False)

        text = f"{anz_angriffe} Angriffe verarbeitet\n{anz_tabs} Tabs gefunden"
        label = ttk.Label(popup, text=text, font=("Segoe UI", 11))
        label.pack(pady=20)

        button = ttk.Button(popup, text="OK", command=popup.destroy)
        button.pack(pady=(0, 10))

    @staticmethod
    def lade_koord_to_id_map(welt_id: str) -> Dict[str, int]:
        url = f"https://de{welt_id}.die-staemme.de/map/village.txt.gz"
        response = requests.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"Download der Dorfdaten fehlgeschlagen (Status: {response.status_code}, URL: {url})")

        gzip_file = gzip.GzipFile(fileobj=BytesIO(response.content))
        content = gzip_file.read().decode("utf-8")

        koord_to_id_map = {}
        for line in content.strip().splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 4:
                village_id = int(parts[0])
                x = parts[2]
                y = parts[3]
                coord = f"{x}|{y}"
                koord_to_id_map[coord] = village_id

        return koord_to_id_map

    @staticmethod
    def export_dsultimate(matches: list, welt_id: str) -> str:
        ds_names = {
            "Speerträger": "spear",
            "Schwertkämpfer": "sword",
            "Axtkämpfer": "axe",
            "Späher": "spy",
            "Leichte Kavallerie": "light",
            "Schwere Kavallerie": "heavy",
            "Rammböcke": "ram",
            "Katapulte": "catapult"
        }

        koord_to_id = TabMatching.lade_koord_to_id_map(welt_id)
        result = []

        for match in matches:
            start_id = koord_to_id.get(match.herkunft.koordinaten)
            ziel_id = koord_to_id.get(match.ziel_koord)

            if not start_id or not ziel_id:
                continue

            einheit = ds_names.get(match.einheit_kuerzel, match.einheit_kuerzel.lower())

            timestamp_ms = int(match.ankunftszeit.timestamp() * 1000)

            einheiten = {
                ds_names.get(name, ""): base64.b64encode(str(anzahl).encode("utf-8")).decode("utf-8")
                for name, anzahl in match.einheiten.items()
            }

            alle_ds_keys = [
                "spear", "sword", "axe", "archer", "spy",
                "light", "marcher", "heavy", "ram",
                "catapult", "knight", "snob", "militia"
            ]
            einheitencode = "/".join([
                f"{ein}={einheiten.get(ein, 'MA==')}" for ein in alle_ds_keys
            ])

            line = f"{start_id}&{ziel_id}&{einheit}&{timestamp_ms}&0&false&false&{einheitencode}"
            result.append(line)

        return "\n".join(result)
