"""Schnitt-Uebersicht fuer das Fenster: welcher Schnitt steht wo im Ablauf?

Fuehrt drei Quellen zu einer Zeile pro Schnitt zusammen:

1. Schnitt-Definitionen aus den Benutzerattributen (Cadwork-Modell)
2. Zwischendateien (.ifccut.json) in der Ablage neben der 3D-Datei
3. bereits importierte Schnitte im 3D (Import-Marker-Attribut)

und leitet daraus den Status je Schnitt und den naechsten sinnvollen
Schritt fuer den Anwender ab (Definieren -> Generieren -> Importieren).

Reines Python ohne Cadwork- und Tk-Importe, damit es ohne Cadwork
getestet werden kann (tests/unit/test_uebersicht.py). Die Daten selbst
liest das Fenster (app/main_window.py) auf dem Cadwork-Hauptthread.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from ifc_schnitt_importer.shared.schnitt_definition import SchnittDefinition, SchnittDefinitionFehler
from ifc_schnitt_importer.shared.schnitt_format import exchange_dateiname, sicherer_dateiname

# Status je Schnitt (Reihenfolge = Ablauf)
FEHLER = "fehler"              # Definition im Attribut fehlerhaft
NICHT_GENERIERT = "offen"      # Definition ok, noch keine Zwischendatei
VERALTET = "veraltet"          # Zwischendatei aelter als die gewaehlte IFC
BEREIT = "bereit"              # Zwischendatei da, Schnitt noch nicht im 3D
IM_3D = "im_3d"                # Schnitt ist im 3D
NUR_ABLAGE = "nur_ablage"      # Zwischendatei ohne (passende) Definition im Modell

STATUS_TEXTE = {
    FEHLER: "Definition fehlerhaft",
    NICHT_GENERIERT: "Noch nicht generiert",
    VERALTET: "IFC ist neuer – neu generieren",
    BEREIT: "Bereit zum Import",
    IM_3D: "Im 3D",
    NUR_ABLAGE: "Nur in Ablage (keine Definition)",
}

# Naechster Schritt fuer den Anwender
SCHRITT_DEFINIEREN = "definieren"
SCHRITT_IFC_WAEHLEN = "ifc_waehlen"
SCHRITT_GENERIEREN = "generieren"
SCHRITT_IMPORTIEREN = "importieren"
SCHRITT_FERTIG = "fertig"

# Schrittleiste oben im Fenster: (Schluessel, Titel)
SCHRITTE = (
    ("definieren", "Schnitte definieren"),
    ("generieren", "Aus IFC generieren"),
    ("importieren", "Ins 3D importieren"),
)

ERLEDIGT = "erledigt"
AKTIV = "aktiv"
OFFEN = "offen"


@dataclass
class SchnittZeile:
    """Eine Zeile der Schnitt-Tabelle."""

    schluessel: str                      # eindeutig je Schnitt (bereinigter Name, klein)
    name: str
    status: str
    typ: str = ""                        # "horizontal" | "vertikal" | ""
    ebene: str = ""                      # Kurzbeschreibung der Schnittebene
    element_id: Optional[int] = None     # Element mit der Definition
    datei: Optional[str] = None          # Zwischendatei, falls vorhanden
    generiert_am: Optional[float] = None  # mtime der Zwischendatei
    im_3d: bool = False
    meldung: str = ""                    # Fehlertext (Status FEHLER)

    @property
    def importierbar(self) -> bool:
        return self.datei is not None

    @property
    def status_text(self) -> str:
        return STATUS_TEXTE.get(self.status, self.status)


@dataclass
class Uebersicht:
    zeilen: List[SchnittZeile] = field(default_factory=list)

    def mit_status(self, *status: str) -> List[SchnittZeile]:
        return [z for z in self.zeilen if z.status in status]

    @property
    def anzahl_definitionen(self) -> int:
        return len([z for z in self.zeilen if z.status not in (FEHLER, NUR_ABLAGE)])

    def zeile(self, schluessel: str) -> Optional[SchnittZeile]:
        for z in self.zeilen:
            if z.schluessel == schluessel:
                return z
        return None


def schnitt_schluessel(name: str) -> str:
    """Vergleichsschluessel wie bei der Duplikat-Pruefung im Generator-Service."""

    return sicherer_dateiname(name).casefold()


def _zahl(wert: float) -> str:
    return f"{wert:.0f}" if abs(wert - round(wert)) < 1e-6 else f"{wert:.1f}"


def ebene_text(definition: SchnittDefinition) -> str:
    """Kurze, lesbare Lage der Schnittebene fuer die Tabelle."""

    ux, uy, uz = definition.ursprung
    if definition.typ == "horizontal":
        return f"Höhe Z = {_zahl(uz)} mm"
    rx, ry, _ = definition.richtung
    if abs(ry) < 1e-9:
        return f"Ebene X = {_zahl(ux)} mm"
    if abs(rx) < 1e-9:
        return f"Ebene Y = {_zahl(uy)} mm"
    return f"durch {_zahl(ux)} / {_zahl(uy)}, Normale {_zahl(rx)},{_zahl(ry)}"


def zeit_text(zeitstempel: Optional[float]) -> str:
    if not zeitstempel:
        return "–"
    return datetime.datetime.fromtimestamp(zeitstempel).strftime("%d.%m.%Y %H:%M")


def _name_aus_dateiname(dateiname: str, projekt_nummer: str, suffix: str) -> str:
    name = dateiname[: -len(suffix)] if dateiname.endswith(suffix) else dateiname
    praefix = f"{sicherer_dateiname(projekt_nummer or '')}_"
    if name.startswith(praefix):
        name = name[len(praefix):]
    return name


def baue_uebersicht(
    definitionen: Iterable[SchnittDefinition],
    definition_fehler: Iterable[SchnittDefinitionFehler],
    dateien: Iterable[str],
    importierte_namen: Iterable[str],
    projekt_nummer: str,
    datei_suffix: str = ".ifccut.json",
    ifc_geaendert_am: Optional[float] = None,
    mtime: Callable[[str], float] = os.path.getmtime,
) -> Uebersicht:
    """Fuehrt Definitionen, Zwischendateien und Importe zu Zeilen zusammen.

    - ``dateien``: Pfade der vorhandenen Zwischendateien in der Ablage
    - ``importierte_namen``: Schnittnamen, die im 3D bereits importiert sind
    - ``ifc_geaendert_am``: mtime der gewaehlten IFC; ist eine Zwischendatei
      aelter, gilt der Schnitt als veraltet
    """

    dateien_nach_name: Dict[str, str] = {os.path.basename(p).casefold(): p for p in dateien}
    importiert = {schnitt_schluessel(n) for n in importierte_namen if n}

    def _mtime(pfad: str) -> Optional[float]:
        try:
            return mtime(pfad)
        except OSError:
            return None

    zeilen: List[SchnittZeile] = []
    benutzte_dateien = set()

    for definition in sorted(definitionen, key=lambda d: d.name.casefold()):
        schluessel = schnitt_schluessel(definition.name)
        dateiname = exchange_dateiname(projekt_nummer, definition.name, datei_suffix).casefold()
        datei = dateien_nach_name.get(dateiname)
        generiert_am = _mtime(datei) if datei else None
        if datei:
            benutzte_dateien.add(dateiname)
        im_3d = schluessel in importiert

        if datei is None:
            status = NICHT_GENERIERT
        elif ifc_geaendert_am is not None and generiert_am is not None and generiert_am < ifc_geaendert_am:
            status = VERALTET
        elif im_3d:
            status = IM_3D
        else:
            status = BEREIT

        zeilen.append(
            SchnittZeile(
                schluessel=schluessel,
                name=definition.name,
                status=status,
                typ=definition.typ,
                ebene=ebene_text(definition),
                element_id=definition.source_element_id,
                datei=datei,
                generiert_am=generiert_am,
                im_3d=im_3d,
            )
        )

    # Zwischendateien ohne Definition (z.B. Definition inzwischen geloescht)
    for dateiname, pfad in sorted(dateien_nach_name.items()):
        if dateiname in benutzte_dateien:
            continue
        name = _name_aus_dateiname(os.path.basename(pfad), projekt_nummer, datei_suffix)
        schluessel = schnitt_schluessel(name)
        zeilen.append(
            SchnittZeile(
                schluessel=f"datei:{dateiname}",
                name=name,
                status=NUR_ABLAGE,
                datei=pfad,
                generiert_am=_mtime(pfad),
                im_3d=schluessel in importiert,
            )
        )

    for index, fehler in enumerate(definition_fehler):
        zeilen.append(
            SchnittZeile(
                schluessel=f"fehler:{index}",
                name=f"Element {fehler.element_id}",
                status=FEHLER,
                element_id=fehler.element_id,
                meldung=fehler.fehler,
            )
        )

    return Uebersicht(zeilen=zeilen)


def naechster_schritt(uebersicht: Uebersicht, ifc_gewaehlt: bool) -> str:
    """Was soll der Anwender als Naechstes tun?"""

    if uebersicht.anzahl_definitionen == 0 and not uebersicht.mit_status(NUR_ABLAGE):
        return SCHRITT_DEFINIEREN
    if uebersicht.mit_status(NICHT_GENERIERT, VERALTET):
        return SCHRITT_GENERIEREN if ifc_gewaehlt else SCHRITT_IFC_WAEHLEN
    if uebersicht.mit_status(BEREIT):
        return SCHRITT_IMPORTIEREN
    return SCHRITT_FERTIG


def schritt_zustaende(schritt: str) -> Dict[str, str]:
    """Zustand der drei Schritte in der Schrittleiste (erledigt / aktiv / offen)."""

    if schritt == SCHRITT_DEFINIEREN:
        return {"definieren": AKTIV, "generieren": OFFEN, "importieren": OFFEN}
    if schritt in (SCHRITT_IFC_WAEHLEN, SCHRITT_GENERIEREN):
        return {"definieren": ERLEDIGT, "generieren": AKTIV, "importieren": OFFEN}
    if schritt == SCHRITT_IMPORTIEREN:
        return {"definieren": ERLEDIGT, "generieren": ERLEDIGT, "importieren": AKTIV}
    return {"definieren": ERLEDIGT, "generieren": ERLEDIGT, "importieren": ERLEDIGT}


HINWEISE = {
    SCHRITT_DEFINIEREN: (
        "Im Modell sind noch keine Schnitte definiert. Einen Schnitt als Benutzerattribut 20–29 "
        "an ein Element schreiben (siehe «Hilfe») und dann «Aktualisieren»."
    ),
    SCHRITT_IFC_WAEHLEN: "Als Nächstes die IFC-Datei des Architekten wählen.",
    SCHRITT_GENERIEREN: "Als Nächstes «Schnitte generieren» – berechnet alle Schnitte aus der IFC.",
    SCHRITT_IMPORTIEREN: "Als Nächstes die gewünschten Schnitte anhaken und «Importieren».",
    SCHRITT_FERTIG: "Alle Schnitte sind im 3D. Nach einer neuen IFC einfach erneut generieren.",
}


def standard_auswahl(uebersicht: Uebersicht) -> List[str]:
    """Welche Zeilen beim Anzeigen fuer den Import angehakt sind: alle, die bereit sind."""

    return [z.schluessel for z in uebersicht.mit_status(BEREIT)]
