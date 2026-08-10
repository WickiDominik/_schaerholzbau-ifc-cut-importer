"""Business logic for the IFC Schnitt Importer.

STATUS: Etappe 4 (implementiert, erster Cadwork-Live-Test steht noch
aus - siehe docs/konzept.md). Liest eine vom generator_tool erzeugte
.ifccut.json und erzeugt Flaechen (create_polygon_panel) + Linien
(create_line_points) an der IFC-Originalposition, in einer eigenen
Gruppe je Schnitt. Ein erneuter Import desselben Schnitts ersetzt die
zuvor importierte Geometrie (ueber ein Benutzerattribut wiedergefunden).
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import List

from ifc_schnitt_importer.app.config import PathConfig, ReferenceGeometryConfig
from ifc_schnitt_importer.cadwork_api import attributes as ac
from ifc_schnitt_importer.cadwork_api import elements as ec
from ifc_schnitt_importer.cadwork_api import visualization as vc
from ifc_schnitt_importer.shared.schnitt_format import SchnittErgebnis, load_schnitt_ergebnis
from ifc_schnitt_importer.shared.vector_math import normalize, subtract


@dataclass
class SchnittImportFehler:
    beschreibung: str


@dataclass
class SchnittImportErgebnis:
    schnitt_name: str
    ersetzte_alte_elemente: int
    erzeugte_flaechen: int
    erzeugte_linien: int
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

    def import_schnitt(self, ergebnis: SchnittErgebnis) -> SchnittImportErgebnis:
        self.ensure_attribute_label()

        old_ids = self._find_previous_import(ergebnis.schnitt_name)
        if old_ids:
            ec.delete_elements_with_undo(old_ids)

        normal = normalize(tuple(ergebnis.ebene.normal))

        flaeche_ids: List[int] = []
        linie_ids: List[int] = []
        fehler: List[SchnittImportFehler] = []

        for flaeche in ergebnis.flaechen:
            vertices = [tuple(v) for v in flaeche.vertices]
            if len(vertices) < 3:
                continue
            x_direction = self._safe_x_direction(vertices, normal)
            try:
                eid = ec.create_polygon_panel(vertices, ReferenceGeometryConfig.SURFACE_THICKNESS_MM, x_direction, normal)
                flaeche_ids.append(eid)
            except Exception as e:
                fehler.append(SchnittImportFehler(f"Flaeche ({flaeche.ifc_element_type} {flaeche.ifc_guid}): {e}"))

        for linie in ergebnis.linien:
            try:
                eid = ec.create_line_points(tuple(linie.start), tuple(linie.end))
                linie_ids.append(eid)
            except Exception as e:
                fehler.append(SchnittImportFehler(f"Linie ({linie.ifc_element_type} {linie.ifc_guid}): {e}"))

        all_new_ids = flaeche_ids + linie_ids
        if all_new_ids:
            group_name = f"{ReferenceGeometryConfig.GROUP_PREFIX} - {ergebnis.schnitt_name}"
            try:
                ac.set_group(all_new_ids, group_name)
                ac.set_name(all_new_ids, ergebnis.schnitt_name)
                ac.set_comment(all_new_ids, ReferenceGeometryConfig.COMMENT_TAG)
                ac.set_user_attribute(all_new_ids, ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER, ergebnis.schnitt_name)
            except Exception as e:
                fehler.append(SchnittImportFehler(f"Gruppierung/Attribute konnten nicht gesetzt werden: {e}"))

            try:
                if flaeche_ids:
                    vc.set_color(flaeche_ids, ReferenceGeometryConfig.SURFACE_COLOR)
                if linie_ids:
                    vc.set_color(linie_ids, ReferenceGeometryConfig.LINE_COLOR)
            except Exception as e:
                fehler.append(SchnittImportFehler(f"Farbe konnte nicht gesetzt werden: {e}"))

        return SchnittImportErgebnis(
            schnitt_name=ergebnis.schnitt_name,
            ersetzte_alte_elemente=len(old_ids),
            erzeugte_flaechen=len(flaeche_ids),
            erzeugte_linien=len(linie_ids),
            fehler=fehler,
        )

    @staticmethod
    def _safe_x_direction(vertices, normal) -> tuple:
        """Eine In-Ebene-Richtung fuer die lokale X-Achse des Panels.

        Nimmt die erste Polygonkante; bei (praktisch) entarteten
        Polygonen faellt sie auf eine beliebige zur Normalen senkrechte
        Richtung zurueck, damit create_polygon_panel nie an einem
        Nullvektor scheitert.
        """

        for i in range(len(vertices) - 1):
            edge = subtract(vertices[i + 1], vertices[i])
            if edge != (0.0, 0.0, 0.0):
                try:
                    return normalize(edge)
                except ValueError:
                    continue

        # Fallback: irgendein Vektor senkrecht zur Normalen.
        fallback = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
        cross = (
            normal[1] * fallback[2] - normal[2] * fallback[1],
            normal[2] * fallback[0] - normal[0] * fallback[2],
            normal[0] * fallback[1] - normal[1] * fallback[0],
        )
        return normalize(cross)
