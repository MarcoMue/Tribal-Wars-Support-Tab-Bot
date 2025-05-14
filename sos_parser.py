import re
from datetime import datetime
from dataclasses import dataclass
from typing import List
from pytz import timezone

@dataclass
class Angriff:
    ziel_koord: str
    ankunftszeit: datetime
    einheit: str

class SosParser:
    @staticmethod
    def parse(text: str) -> List[Angriff]:
        angriffe = []
        aktives_zieldorf = None

        zeilen = text.splitlines()
        zieldorf_pattern = re.compile(r"\[b\]Dorf:\[/b\]\s*\[coord\](\d{3}\|\d{3})\[/coord\]")
        angriff_pattern = re.compile(
            r"\[command\]attack\[/command\] (.*?) \| .*?\[coord\](\d{3}\|\d{3})\[/coord\] --> Ankunftszeit: (\d{2}\.\d{2}\.\d{2}) (\d{2}:\d{2}:\d{2})"
        )

        berlin = timezone("Europe/Berlin")

        for zeile in zeilen:
            ziel_match = zieldorf_pattern.search(zeile)
            if ziel_match:
                aktives_zieldorf = ziel_match.group(1)
                continue

            angriff_match = angriff_pattern.search(zeile)
            if angriff_match and aktives_zieldorf:
                einheit = angriff_match.group(1).strip()
                datum = angriff_match.group(3)
                uhrzeit = angriff_match.group(4)
                try:
                    dt = datetime.strptime(datum + " " + uhrzeit, "%d.%m.%y %H:%M:%S")
                    ankunft = berlin.localize(dt)
                    angriffe.append(Angriff(ziel_koord=aktives_zieldorf, ankunftszeit=ankunft, einheit=einheit))
                except ValueError:
                    print(f"Fehler beim Parsen: {datum} {uhrzeit}")

        return angriffe
