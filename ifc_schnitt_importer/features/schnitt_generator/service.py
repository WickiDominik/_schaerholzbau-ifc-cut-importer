"""Business logic for the IFC Schnitt Generator.

STATUS: Etappe 1 (Skeleton). The methods below define the intended flow
and are the concrete implementation targets for Etappe 2/3 - see
docs/konzept.md for the staged plan and docs/api_spike_ergebnisse.md
(created after Etappe 0) for the confirmed Cadwork API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ifc_schnitt_importer.shared.schnitt_format import SchnittEbene, SchnittErgebnis


@dataclass
class AusgabeelementKandidat:
    """One selectable Cadwork Ausgabeelement/Achse, shown in the UI."""

    element_id: int
    name: str
    schnitt_typ: str  # "horizontal" | "vertikal"


class SchnittGeneratorService:
    """Coordinates IFC import and Schnitt computation.

    Etappe 2 implements `list_ausgabeelemente` + `get_schnittebene`.
    Etappe 3 implements `import_ifc` + `berechne_schnitt`.
    """

    def list_ausgabeelemente(self) -> List[AusgabeelementKandidat]:
        """Return Ausgabeelemente/Achsen currently in the model to choose from.

        TODO (Etappe 2): implement via element selection + geometry_controller
        (get_p1/get_xl/get_yl/get_zl), pending Etappe 0 verification.
        """

        raise NotImplementedError("Etappe 2: Ausgabeelement-Auswahl")

    def get_schnittebene(self, element_id: int) -> SchnittEbene:
        """Derive a cutting plane (origin + normal) from a chosen element.

        TODO (Etappe 2).
        """

        raise NotImplementedError("Etappe 2: Schnittebene-Extraktion")

    def import_ifc(self, ifc_file_path: str) -> List[int]:
        """Import the IFC file via bim_controller and return exchange object ids.

        TODO (Etappe 3): ifc_schnitt_importer.cadwork_api.bim.import_ifc_return_exchange_objects
        """

        raise NotImplementedError("Etappe 3: IFC-Import")

    def berechne_schnitt(
        self,
        schnitt_name: str,
        schnitt_typ: str,
        ebene: SchnittEbene,
        exchange_object_ids: List[int],
        ifc_file_path: str,
        projekt_nummer: str,
    ) -> SchnittErgebnis:
        """Compute the cross-section geometry for one Schnitt.

        TODO (Etappe 3): convert relevant exchange objects, cut them with
        the plane, collect resulting Flaechen/Linien.
        """

        raise NotImplementedError("Etappe 3: Schnittberechnung")
