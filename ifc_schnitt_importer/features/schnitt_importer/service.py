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
- je restlichem offenem Liniensegment (Sonderfall, siehe
  schnitt_berechnung.py - eine Kette OHNE zugehoerige Flaeche) weiterhin
  einzelne create_line_points-Elemente.

Alle erzeugten Elemente bekommen BUG (Bauuntergruppe) =
ReferenceGeometryConfig.BAUUNTERGRUPPE ("Grundrisse/Schnitte", gleiche
Konvention wie shb_toolcenter.cut_handling) und BG (Baugruppe) = der
Schnittname. Ein erneuter Import desselben Schnitts ersetzt die zuvor
importierte Geometrie (ueber ein Benutzerattribut wiedergefunden).

Ausfuehrliche Meldungen (Fehler je Flaeche/Linie, Fortschritt) gehen NUR
noch per print() an die Cadwork-Konsole - das UI zeigt lediglich eine
kurze Zusammenfassung (SchnittImportErgebnis), siehe app/main_window.py.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

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

    def _find_previous_import(self, schnitt_name: str) -> List[int]:
        """Elemente eines frueheren Imports desselben Schnitts finden."""

        found = []
        for element_id in ec.get_all_identifiable_element_ids():
            try:
                marker = ac.get_user_attribute(element_id, ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER)
            except Exception:
                continue
            if marker == schnitt_name:
                found.append(element_id)
        return found

    def import_schnitt(self, ergebnis: SchnittErgebnis, progress_callback: ProgressCallback = None) -> SchnittImportErgebnis:
        def report(current: int, total: int, message: str) -> None:
            print(f"[schnitt_importer] {message} ({current}/{total})")
            if progress_callback is not None:
                progress_callback(current, total, message)

        self.ensure_attribute_label()

        report(0, 1, f"Suche vorherigen Import von '{ergebnis.schnitt_name}' ...")
        old_ids = self._find_previous_import(ergebnis.schnitt_name)
        if old_ids:
            ec.delete_elements_with_undo(old_ids)

        flaeche_ids: List[int] = []
        linie_ids: List[int] = []
        fehler: List[SchnittImportFehler] = []

        gesamt = len(ergebnis.flaechen) + len(ergebnis.linien)
        verarbeitet = 0

        for flaeche in ergebnis.flaechen:
            vertices = [tuple(v) for v in flaeche.vertices]
            if len(vertices) >= 3:
                # create_surface erzeugt eine FLACHE Referenzflaeche ohne
                # Dicken-Parameter (anders als create_polygon_panel) -
                # passend fuer einen Schnitt/eine Vergleichsreferenz statt
                # eines echten Bauteils. Ob der Umriss geschlossen
                # (Schlusspunkt dupliziert) uebergeben werden muss, ist
                # bisher nicht live verifiziert (anders als bei
                # create_polygon_panel/create_spline_line, die sich
                # gegensaetzlich verhalten haben) - hier zunaechst wie bei
                # create_spline_line NICHT geschlossen versucht.
                try:
                    eid = ec.create_surface(_vertex_list(vertices))
                    flaeche_ids.append(eid)
                except Exception as e:
                    meldung = f"Flaeche ({flaeche.ifc_element_type} {flaeche.ifc_guid}): {e}"
                    print(f"[schnitt_importer] FEHLER {meldung}")
                    fehler.append(SchnittImportFehler(meldung))

            verarbeitet += 1
            if verarbeitet % _PROGRESS_UPDATE_STEP == 0:
                report(verarbeitet, gesamt, f"Erzeuge Flaechen fuer '{ergebnis.schnitt_name}' ...")

        for linie in ergebnis.linien:
            # Restfaelle: offene (nicht geschlossene) Segmentketten, siehe
            # schnitt_berechnung.py - selten, einzeln als Linie erzeugt.
            try:
                eid = ec.create_line_points(_point_3d(linie.start), _point_3d(linie.end))
                linie_ids.append(eid)
            except Exception as e:
                meldung = f"Linie ({linie.ifc_element_type} {linie.ifc_guid}): {e}"
                print(f"[schnitt_importer] FEHLER {meldung}")
                fehler.append(SchnittImportFehler(meldung))

            verarbeitet += 1
            if verarbeitet % _PROGRESS_UPDATE_STEP == 0:
                report(verarbeitet, gesamt, f"Erzeuge Restlinien fuer '{ergebnis.schnitt_name}' ...")

        flaechen_verbunden = False
        if len(flaeche_ids) >= 2:
            report(gesamt, gesamt, f"Verbinde {len(flaeche_ids)} Flaechen von '{ergebnis.schnitt_name}' ...")
            try:
                ec.join_elements(flaeche_ids)
                flaechen_verbunden = True
            except Exception as e:
                meldung = f"Flaechen konnten nicht verbunden werden (join_elements): {e}"
                print(f"[schnitt_importer] FEHLER {meldung}")
                fehler.append(SchnittImportFehler(meldung))

        all_new_ids = flaeche_ids + linie_ids
        if all_new_ids:
            try:
                ac.set_group(all_new_ids, ergebnis.schnitt_name)  # BG
                ac.set_subgroup(all_new_ids, ReferenceGeometryConfig.BAUUNTERGRUPPE)  # BUG
                ac.set_name(all_new_ids, ergebnis.schnitt_name)
                ac.set_comment(all_new_ids, ReferenceGeometryConfig.COMMENT_TAG)
                ac.set_user_attribute(all_new_ids, ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER, ergebnis.schnitt_name)
            except Exception as e:
                meldung = f"Gruppierung/Attribute konnten nicht gesetzt werden: {e}"
                print(f"[schnitt_importer] FEHLER {meldung}")
                fehler.append(SchnittImportFehler(meldung))

            try:
                if flaeche_ids:
                    vc.set_color(flaeche_ids, ReferenceGeometryConfig.SURFACE_COLOR)
                if linie_ids:
                    vc.set_color(linie_ids, ReferenceGeometryConfig.LINE_COLOR)
            except Exception as e:
                meldung = f"Farbe konnte nicht gesetzt werden: {e}"
                print(f"[schnitt_importer] FEHLER {meldung}")
                fehler.append(SchnittImportFehler(meldung))

        report(gesamt, gesamt, f"'{ergebnis.schnitt_name}' fertig.")

        return SchnittImportErgebnis(
            schnitt_name=ergebnis.schnitt_name,
            ersetzte_alte_elemente=len(old_ids),
            erzeugte_flaechen=len(flaeche_ids),
            erzeugte_linien=len(linie_ids),
            flaechen_verbunden=flaechen_verbunden,
            fehler=fehler,
        )
