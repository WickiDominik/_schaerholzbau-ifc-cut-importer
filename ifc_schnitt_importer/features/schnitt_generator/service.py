"""Business logic for the Cadwork-side half of the IFC Schnitt Generator.

STATUS: Etappe 2 (implementiert). Die eigentliche IFC-Geometrie-/
Schnittberechnung (frueher hier geplant) laeuft NICHT mehr in Cadwork -
siehe docs/konzept.md, Abschnitt "Warum die Schnittberechnung ausserhalb
von Cadwork passiert". Diese Klasse deckt nur noch den Cadwork-seitigen
Teil ab: Schnitt-Definitionen (Benutzerattribute) aus dem Modell lesen
und als Bruecken-Datei fuer das externe generator_tool/ exportieren.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import List

from ifc_schnitt_importer.app.config import PathConfig, SchnittDefinitionConfig
from ifc_schnitt_importer.cadwork_api import attributes as ac
from ifc_schnitt_importer.cadwork_api import elements as ec
from ifc_schnitt_importer.cadwork_api import project as uc
from ifc_schnitt_importer.shared.schnitt_definition import (
    SchnittDefinition,
    SchnittDefinitionError,
    SchnittDefinitionExport,
    SchnittDefinitionFehler,
)


class SchnittGeneratorService:
    """Cadwork-side step: Schnitt-Definitionen aus dem Modell exportieren."""

    def ensure_attribute_label(self) -> None:
        """Label the configured Benutzerattribut slot so it's recognisable
        in Cadwork's attribute dialog (best-effort, never fails hard)."""

        try:
            ac.set_user_attribute_name(SchnittDefinitionConfig.ATTRIBUTE_NUMBER, SchnittDefinitionConfig.ATTRIBUTE_LABEL)
        except Exception as e:
            print(f"[schnitt_generator] Konnte Attribut-Beschriftung nicht setzen: {e}")

    def scan_schnitt_definitionen(self) -> SchnittDefinitionExport:
        """Scan all identifiable elements for a filled Schnitt-Definition attribute."""

        definitionen: List[SchnittDefinition] = []
        fehler: List[SchnittDefinitionFehler] = []

        element_ids = ec.get_all_identifiable_element_ids()
        for element_id in element_ids:
            try:
                text = ac.get_user_attribute(element_id, SchnittDefinitionConfig.ATTRIBUTE_NUMBER)
            except Exception as e:
                # Best-effort: a single unreadable element must not abort the whole scan.
                fehler.append(SchnittDefinitionFehler(element_id=element_id, fehler=f"Attribut nicht lesbar: {e}"))
                continue

            if not text or not text.strip():
                continue

            try:
                definition = SchnittDefinition.parse_from_text(text, source_element_id=element_id)
                definitionen.append(definition)
            except SchnittDefinitionError as e:
                fehler.append(SchnittDefinitionFehler(element_id=element_id, fehler=str(e)))

        return SchnittDefinitionExport(definitionen=definitionen, fehler=fehler)

    def export_schnitt_definitionen(self) -> tuple[SchnittDefinitionExport, str]:
        """Scan + write the bridging file for the external generator_tool.

        Returns (scan_result, written_file_path).
        """

        result = self.scan_schnitt_definitionen()

        project_3d_file_path = uc.get_3d_file_path()
        target_path = PathConfig.get_schnitt_definitionen_file_path(project_3d_file_path)

        import os

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        payload = {
            "projekt_nummer": uc.get_project_number(),
            "quelle_3d_datei": project_3d_file_path,
            "definitionen": [asdict(d) for d in result.definitionen],
        }
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return result, target_path
