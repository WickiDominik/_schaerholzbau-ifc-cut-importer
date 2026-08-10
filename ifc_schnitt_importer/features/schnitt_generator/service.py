"""Business logic for die IFC Schnitt Generator (Cadwork-Seite).

STATUS: Etappe 2 + 5 (implementiert). Deckt beide Cadwork-seitigen
Schritte ab:

1. Schnitt-Definitionen (Benutzerattribute) aus dem Modell scannen und
   als Bruecken-Datei fuer das externe generator_tool exportieren.
2. Das externe generator_tool (eigene Python-Umgebung, siehe
   generator_tool/README.md) als Subprozess anstossen, damit der
   Anwender die ganze Kette (IFC waehlen -> Schnitte berechnen) direkt
   aus dem Cadwork-Fenster ausloesen kann, ohne selbst ein Terminal zu
   bedienen.

Die eigentliche IFC-Geometrie-/Schnittberechnung passiert weiterhin
NICHT in Cadwork - siehe docs/konzept.md, Abschnitt "Warum die
Schnittberechnung ausserhalb von Cadwork passiert".
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from typing import List

from ifc_schnitt_importer.app.bootstrap import project_root
from ifc_schnitt_importer.app.config import GeneratorToolConfig, PathConfig, SchnittDefinitionConfig
from ifc_schnitt_importer.cadwork_api import attributes as ac
from ifc_schnitt_importer.cadwork_api import elements as ec
from ifc_schnitt_importer.cadwork_api import project as uc
from ifc_schnitt_importer.shared.schnitt_definition import (
    SchnittDefinition,
    SchnittDefinitionExport,
    SchnittDefinitionFehler,
)


class GeneratorToolNichtEingerichtetError(RuntimeError):
    """Die venv des externen generator_tool wurde noch nicht angelegt."""


@dataclass
class SchnitteGenerierenErgebnis:
    definitionen_export: SchnittDefinitionExport
    definitionen_datei: str
    ifc_datei: str
    subprocess_erfolgreich: bool
    subprocess_ausgabe: str
    erzeugte_dateien: List[str] = field(default_factory=list)


class SchnittGeneratorService:
    """Cadwork-seitiger Teil: Schnitt-Definitionen exportieren + das
    externe generator_tool anstossen."""

    # ---- Schritt 1: Schnitt-Definitionen aus Benutzerattributen ----

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
                fehler.append(SchnittDefinitionFehler(element_id=element_id, fehler=f"Attribut nicht lesbar: {e}"))
                continue

            if not text or not text.strip():
                continue

            geparste, zeilen_fehler = SchnittDefinition.parse_multiple_from_text(text, source_element_id=element_id)
            definitionen.extend(geparste)
            for meldung in zeilen_fehler:
                fehler.append(SchnittDefinitionFehler(element_id=element_id, fehler=meldung))

        return SchnittDefinitionExport(definitionen=definitionen, fehler=fehler)

    def export_schnitt_definitionen(self) -> tuple[SchnittDefinitionExport, str]:
        """Scan + write the bridging file for the external generator_tool.

        Returns (scan_result, written_file_path).
        """

        result = self.scan_schnitt_definitionen()

        project_3d_file_path = uc.get_3d_file_path()
        target_path = PathConfig.get_schnitt_definitionen_file_path(project_3d_file_path)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        payload = {
            "projekt_nummer": uc.get_project_number(),
            "quelle_3d_datei": project_3d_file_path,
            "definitionen": [asdict(d) for d in result.definitionen],
        }
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return result, target_path

    # ---- Schritt 2: externes generator_tool anstossen ----

    def _venv_python_path(self) -> str:
        return os.path.join(project_root(), GeneratorToolConfig.RELATIVE_VENV_PYTHON)

    def _cli_script_path(self) -> str:
        return os.path.join(project_root(), GeneratorToolConfig.RELATIVE_CLI_SCRIPT)

    def generator_tool_verfuegbar(self) -> bool:
        return os.path.isfile(self._venv_python_path())

    def generate_schnitte(self, ifc_datei: str) -> SchnitteGenerierenErgebnis:
        """Exportiert frische Schnitt-Definitionen und laesst das externe
        generator_tool daraus + der gewaehlten IFC die Schnitte berechnen.
        """

        if not os.path.isfile(ifc_datei):
            raise FileNotFoundError(f"IFC-Datei nicht gefunden: {ifc_datei}")

        venv_python = self._venv_python_path()
        if not os.path.isfile(venv_python):
            raise GeneratorToolNichtEingerichtetError(
                "Das externe Generator-Tool ist noch nicht eingerichtet.\n"
                f"Erwartet wird eine Python-Umgebung unter:\n  {venv_python}\n\n"
                "Einmalig einrichten (siehe generator_tool/README.md):\n"
                "  cd generator_tool\n"
                "  python -m venv .venv\n"
                "  .venv\\Scripts\\pip install -r requirements.txt"
            )

        self.ensure_attribute_label()
        definitionen_export, definitionen_datei = self.export_schnitt_definitionen()

        output_dir = os.path.dirname(definitionen_datei)

        cli_script = self._cli_script_path()
        args = [
            venv_python,
            cli_script,
            "--ifc", ifc_datei,
            "--definitionen", definitionen_datei,
            "--output", output_dir,
        ]

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            completed = subprocess.run(
                args,
                cwd=project_root(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=GeneratorToolConfig.SUBPROCESS_TIMEOUT_SECONDS,
            )
            ausgabe = (completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")
            erfolgreich = completed.returncode == 0
        except subprocess.TimeoutExpired as e:
            ausgabe = f"Zeitueberschreitung nach {GeneratorToolConfig.SUBPROCESS_TIMEOUT_SECONDS}s: {e}"
            erfolgreich = False

        erzeugte_dateien = []
        if erfolgreich:
            projekt_nummer = uc.get_project_number()
            for definition in definitionen_export.definitionen:
                erwartete_datei = PathConfig.get_exchange_file_path(uc.get_3d_file_path(), projekt_nummer, definition.name)
                if os.path.isfile(erwartete_datei):
                    erzeugte_dateien.append(erwartete_datei)

        return SchnitteGenerierenErgebnis(
            definitionen_export=definitionen_export,
            definitionen_datei=definitionen_datei,
            ifc_datei=ifc_datei,
            subprocess_erfolgreich=erfolgreich,
            subprocess_ausgabe=ausgabe,
            erzeugte_dateien=erzeugte_dateien,
        )
