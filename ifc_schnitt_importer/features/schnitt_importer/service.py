"""Business logic for the IFC Schnitt Importer.

STATUS: Etappe 4/6 (implementiert, mehrfach live getestet - siehe
docs/konzept.md). Liest eine vom generator_tool erzeugte .ifccut.json
und erzeugt:

- je Flaeche eine flache Referenzflaeche (create_surface, OHNE Dicke -
  es handelt sich um einen Schnitt/Vergleichsreferenz, kein reales
  Bauteil, daher kein Panel/Platte mit Materialstaerke). Alle Flaechen
  eines Schnitts werden anschliessend ueber element_controller.
  join_elements zu einem zusammenhaengenden Element verbunden.
- KEINE eigene Kontur-Linie je Flaeche mehr: eine gefuellte Flaeche
  zeigt ihren Umriss in Cadwork bereits selbst, eine zusaetzliche
  Linien-Umrandung waere redundant (auf Anwenderwunsch entfernt).
- je Liniensegment einzelne create_line_points-Elemente: Lochkonturen
  (innere Ringe, z.B. Aussparungen, Hohlprofile) und offene Ketten,
  siehe schnitt_berechnung.py.

Alle erzeugten Elemente bekommen BUG (Bauuntergruppe) =
ReferenceGeometryConfig.BAUUNTERGRUPPE ("Grundrisse/Schnitte", gleiche
Konvention wie shb_toolcenter.cut_handling) und BG (Baugruppe) = der
Schnittname. Ein erneuter Import desselben Schnitts ersetzt die zuvor
importierte Geometrie (ueber ein Benutzerattribut wiedergefunden), aber
erst nachdem die neue Geometrie erzeugt wurde.

Ausfuehrliche Meldungen (Fehler je Flaeche/Linie, Fortschritt) gehen NUR
noch per print() an die Cadwork-Konsole - das UI zeigt lediglich eine
kurze Zusammenfassung (SchnittImportErgebnis), siehe app/main_window.py.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set

from ifc_schnitt_importer.app.config import PathConfig, ReferenceGeometryConfig
from ifc_schnitt_importer.cadwork_api import attributes as ac
from ifc_schnitt_importer.cadwork_api import cadwork_core as cw
from ifc_schnitt_importer.cadwork_api import elements as ec
from ifc_schnitt_importer.cadwork_api import visualization as vc
from ifc_schnitt_importer.shared.schnitt_format import SchnittErgebnis, load_schnitt_ergebnis

# progress_callback(current: int, total: int, message: str) -> None
ProgressCallback = Optional[Callable[[int, int, str], None]]

# Alle wie viele verarbeitete Elemente die UI ueber den Fortschritt
# informiert wird - bei tausenden Flaechen (grosse Projekte) wuerde ein
# Callback je Element das UI unnoetig ausbremsen.
_PROGRESS_UPDATE_STEP = 20


def _point_3d(p):
    """Plain (x, y, z) -> cadwork.point_3d.

    Die Cadwork-API-Funktionen erwarten ihre eigenen pybind11-Typen
    (cadwork.point_3d, cadwork.vertex_list), keine reinen Python-Tupel/
    Listen - siehe docs/konzept.md, Etappe 6 Livetest-Erkenntnisse.
    """

    return cw.point_3d(p[0], p[1], p[2])


def _vertex_list(points):
    vertices = cw.vertex_list()
    for p in points:
        vertices.append(_point_3d(p))
    return vertices


@dataclass
class SchnittImportFehler:
    beschreibung: str


@dataclass
class SchnittImportErgebnis:
    schnitt_name: str
    ersetzte_alte_elemente: int
    erzeugte_flaechen: int
    erzeugte_linien: int
    flaechen_verbunden: bool = False
    fehler: List[SchnittImportFehler] = field(default_factory=list)


class SchnittImporterService:
    def list_available_exchange_files(self, project_3d_file_path: str) -> List[str]:
        directory = PathConfig.get_exchange_directory(project_3d_file_path)
        if not os.path.isdir(directory):
            return []
        pattern = os.path.join(directory, f"*{PathConfig.EXCHANGE_FILE_SUFFIX}")
        return sorted(glob.glob(pattern))

    def load(self, file_path: str) -> SchnittErgebnis:
        return load_schnitt_ergebnis(file_path)

    def ensure_attribute_label(self) -> None:
        try:
            ac.set_user_attribute_name(
                ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER,
                ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_LABEL,
            )
        except Exception as e:
            print(f"[schnitt_importer] Konnte Attribut-Beschriftung nicht setzen: {e}")

    def importierte_schnitt_namen(self) -> Set[str]:
        """Namen aller Schnitte, die im 3D bereits importiert sind (Cadwork-API, nur Hauptthread).

        Fuer die Status-Spalte im Fenster. Ein Lesezugriff je Element auf
        den Marker-Slot; Legacy-Slots zaehlen wie in _find_previous_import
        nur zusammen mit dem Import-Kommentar.
        """

        namen: Set[str] = set()
        for element_id in ec.get_all_identifiable_element_ids():
            for number in self._marker_numbers():
                try:
                    wert = ac.get_user_attribute(element_id, number)
                except Exception:
                    continue
                if not wert or not wert.strip():
                    continue
                if number != ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER and not self._ist_import_element(element_id):
                    continue
                namen.add(wert.strip())
                break
        return namen

    def _marker_numbers(self) -> List[int]:
        return [ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER, *ReferenceGeometryConfig.LEGACY_IMPORT_MARKER_ATTRIBUTE_NUMBERS]

    def _find_previous_import(self, schnitt_name: str) -> List[int]:
        """Elemente eines frueheren Imports desselben Schnitts finden.

        Prueft die aktuelle Marker-Nummer UND fruehere Nummern (siehe
        ReferenceGeometryConfig.LEGACY_IMPORT_MARKER_ATTRIBUTE_NUMBERS),
        damit Importe aus aelteren Plugin-Versionen ebenfalls ersetzt
        werden. Ein Treffer im Legacy-Slot zaehlt nur zusammen mit dem
        Import-Kommentar - dort (21) koennten sonst auch Schnitt-
        Definitionen stehen.
        """

        all_ids = ec.get_all_identifiable_element_ids()
        found: List[int] = []
        seen = set()
        for number in self._marker_numbers():
            for element_id in self._elements_with_user_attribute(all_ids, number, schnitt_name):
                if element_id in seen:
                    continue
                if number != ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER and not self._ist_import_element(element_id):
                    continue
                seen.add(element_id)
                found.append(element_id)
        return found

    @staticmethod
    def _ist_import_element(element_id: int) -> bool:
        try:
            return ac.get_comment(element_id) == ReferenceGeometryConfig.COMMENT_TAG
        except Exception:
            return False

    @staticmethod
    def _elements_with_user_attribute(all_ids, number: int, value: str) -> List[int]:
        """Elemente mit Benutzerattribut `number` == `value`.

        Bevorzugt ueber ec.filter_elements + cadwork.element_filter (ein
        API-Aufruf statt einem je Element); faellt auf die Einzelabfrage
        zurueck, falls der Filter in der installierten Cadwork-Version
        fehlt. Das Ergebnis wird in beiden Faellen exakt nachgeprueft,
        weil nicht dokumentiert ist, ob der Filter exakt oder per
        Teilstring vergleicht.
        """

        candidates = all_ids
        try:
            element_filter = cw.element_filter()
            element_filter.set_user_attribute(number, value)
            candidates = ec.filter_elements(all_ids, element_filter)
        except Exception as e:
            print(f"[schnitt_importer] element_filter nicht verfuegbar, pruefe Elemente einzeln: {e}")

        result = []
        for element_id in candidates:
            try:
                if ac.get_user_attribute(element_id, number) == value:
                    result.append(element_id)
            except Exception:
                continue
        return result

    def import_schnitt(self, ergebnis: SchnittErgebnis, progress_callback: ProgressCallback = None) -> SchnittImportErgebnis:
        """Erzeugt die Referenzgeometrie eines Schnitts.

        Reihenfolge bewusst: (1) frueheren Import nur SUCHEN, (2) neue
        Elemente erzeugen und sofort markieren, (3) erst dann den alten
        Import loeschen. Scheitert die Erzeugung komplett, bleibt der
        alte Import erhalten, statt dass das Modell ohne Schnitt dasteht.
        """

        def report(current: int, total: int, message: str) -> None:
            print(f"[schnitt_importer] {message} ({current}/{total})")
            if progress_callback is not None:
                progress_callback(current, total, message)

        self.ensure_attribute_label()

        report(0, 1, f"Suche vorherigen Import von '{ergebnis.schnitt_name}' ...")
        old_ids = self._find_previous_import(ergebnis.schnitt_name)

        flaeche_ids: List[int] = []
        linie_ids: List[int] = []
        fehler: List[SchnittImportFehler] = []

        def _fehler(meldung: str) -> None:
            print(f"[schnitt_importer] FEHLER {meldung}")
            fehler.append(SchnittImportFehler(meldung))

        gesamt = len(ergebnis.flaechen) + len(ergebnis.linien)
        verarbeitet = 0

        for flaeche in ergebnis.flaechen:
            vertices = [tuple(v) for v in flaeche.vertices]
            if len(vertices) >= 3:
                # create_surface erzeugt eine FLACHE Referenzflaeche ohne
                # Dicken-Parameter (anders als create_polygon_panel) -
                # passend fuer einen Schnitt statt eines echten Bauteils.
                # Der Umriss wird OFFEN uebergeben (Schlusspunkt nicht
                # dupliziert), wie im offiziellen Beispiel der cadwork-API-
                # Doku zu element_controller.create_surface.
                try:
                    eid = ec.create_surface(_vertex_list(vertices))
                    flaeche_ids.append(eid)
                except Exception as e:
                    _fehler(f"Flaeche ({flaeche.ifc_element_type} {flaeche.ifc_guid}): {e}")

            verarbeitet += 1
            if verarbeitet % _PROGRESS_UPDATE_STEP == 0:
                report(verarbeitet, gesamt, f"Erzeuge Flaechen fuer '{ergebnis.schnitt_name}' ...")

        for linie in ergebnis.linien:
            # Offene Segmentketten und Lochkonturen (siehe
            # schnitt_berechnung.py) - einzeln als 2-Punkt-Linie erzeugt.
            try:
                eid = ec.create_line_points(_point_3d(linie.start), _point_3d(linie.end))
                linie_ids.append(eid)
            except Exception as e:
                _fehler(f"Linie ({linie.ifc_element_type} {linie.ifc_guid}): {e}")

            verarbeitet += 1
            if verarbeitet % _PROGRESS_UPDATE_STEP == 0:
                report(verarbeitet, gesamt, f"Erzeuge Linien fuer '{ergebnis.schnitt_name}' ...")

        all_new_ids = flaeche_ids + linie_ids

        if all_new_ids:
            # Marker und Kommentar ZUERST und separat setzen: sie sind die
            # Grundlage, um diesen Import beim naechsten Mal wiederzufinden.
            # Schlaegt danach z.B. set_group fehl, entstehen trotzdem keine
            # unauffindbaren Duplikate.
            try:
                ac.set_user_attribute(all_new_ids, ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER, ergebnis.schnitt_name)
                ac.set_comment(all_new_ids, ReferenceGeometryConfig.COMMENT_TAG)
            except Exception as e:
                _fehler(f"Import-Marker konnte nicht gesetzt werden (erneuter Import ersetzt diese Elemente evtl. nicht): {e}")

            for beschreibung, setter, wert in (
                ("BG (Baugruppe)", ac.set_group, ergebnis.schnitt_name),
                ("BUG (Bauuntergruppe)", ac.set_subgroup, ReferenceGeometryConfig.BAUUNTERGRUPPE),
                ("Name", ac.set_name, ergebnis.schnitt_name),
            ):
                try:
                    setter(all_new_ids, wert)
                except Exception as e:
                    _fehler(f"{beschreibung} konnte nicht gesetzt werden: {e}")

            try:
                if flaeche_ids:
                    vc.set_color(flaeche_ids, ReferenceGeometryConfig.SURFACE_COLOR)
                if linie_ids:
                    vc.set_color(linie_ids, ReferenceGeometryConfig.LINE_COLOR)
            except Exception as e:
                _fehler(f"Farbe konnte nicht gesetzt werden: {e}")

        flaechen_verbunden = False
        if len(flaeche_ids) >= 2:
            report(gesamt, gesamt, f"Verbinde {len(flaeche_ids)} Flaechen von '{ergebnis.schnitt_name}' ...")
            try:
                # join_elements liefert None, die IDs bleiben gueltig
                # (verbundene Elemente, siehe get_joined_elements).
                ec.join_elements(flaeche_ids)
                flaechen_verbunden = True
            except Exception as e:
                _fehler(f"Flaechen konnten nicht verbunden werden (join_elements): {e}")

        # Alten Import erst jetzt entfernen - und nur, wenn der neue
        # Import ueberhaupt etwas erzeugt hat (oder der Schnitt
        # tatsaechlich leer ist).
        ersetzte = 0
        if old_ids:
            if all_new_ids or gesamt == 0:
                try:
                    ec.delete_elements_with_undo(old_ids)
                    ersetzte = len(old_ids)
                except Exception as e:
                    _fehler(f"Alter Import ({len(old_ids)} Elemente) konnte nicht geloescht werden: {e}")
            else:
                _fehler(f"Kein Element neu erzeugt - alter Import ({len(old_ids)} Elemente) bleibt erhalten")

        report(gesamt, gesamt, f"'{ergebnis.schnitt_name}' fertig.")

        return SchnittImportErgebnis(
            schnitt_name=ergebnis.schnitt_name,
            ersetzte_alte_elemente=ersetzte,
            erzeugte_flaechen=len(flaeche_ids),
            erzeugte_linien=len(linie_ids),
            flaechen_verbunden=flaechen_verbunden,
            fehler=fehler,
        )
