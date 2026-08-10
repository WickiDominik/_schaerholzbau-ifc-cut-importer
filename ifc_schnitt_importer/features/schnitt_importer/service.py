"""Business logic for the IFC Schnitt Importer.

STATUS: Etappe 1 (Skeleton). See docs/konzept.md for the staged plan.
"""

from __future__ import annotations

import glob
import os
from typing import List

from ifc_schnitt_importer.app.config import PathConfig
from ifc_schnitt_importer.shared.schnitt_format import SchnittErgebnis, load_schnitt_ergebnis


class SchnittImporterService:
    def list_available_exchange_files(self, project_3d_file_path: str) -> List[str]:
        directory = PathConfig.get_exchange_directory(project_3d_file_path)
        if not os.path.isdir(directory):
            return []
        pattern = os.path.join(directory, f"*{PathConfig.EXCHANGE_FILE_SUFFIX}")
        return sorted(glob.glob(pattern))

    def load(self, file_path: str) -> SchnittErgebnis:
        return load_schnitt_ergebnis(file_path)

    def import_schnitt(self, ergebnis: SchnittErgebnis) -> None:
        """Create Flaechen/Linien reference geometry in the 3D model.

        TODO (Etappe 4): ifc_schnitt_importer.cadwork_api.elements
        create_polygon_panel(...) / create_line_points(...), grouped under
        ReferenceGeometryConfig.GROUP_PREFIX + Schnitt-Name, replacing any
        previous import of the same Schnitt.
        """

        raise NotImplementedError("Etappe 4: Geometrie-Erzeugung")
