"""IFC loading via ifcopenshell.

STATUS: Etappe 3 (Geruest). Ziel: alle raeumlich relevanten Bauteile
(IfcWall(StandardCase), IfcSlab, IfcColumn, IfcBeam, IfcFooting - siehe
docs/konzept.md fuer die vollstaendige/finale Liste) mit ihrer bereits
durch ifcopenshell aufgeloesten Weltkoordinaten-Geometrie laden, inkl.
IfcOpeningElement-Abzuegen (ifcopenshell macht das automatisch mit
`geom.settings(USE_WORLD_COORDS=True)`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

# Bauteilklassen, die in die Schnittberechnung einfliessen. Bewusst OHNE
# Tueren/Fenster (nur Rohbau-relevant fuer den Holzbau-Vergleich) - bei
# Bedarf in Etappe 3 mit dem Anwender erweitern/einschraenken.
RELEVANT_IFC_CLASSES = (
    "IfcWall",
    "IfcWallStandardCase",
    "IfcSlab",
    "IfcColumn",
    "IfcBeam",
    "IfcFooting",
)


@dataclass
class IfcBauteilGeometrie:
    ifc_guid: str
    ifc_type: str
    # Weltkoordinaten-Dreiecksnetz (Liste von Dreiecken, je 3 Punkte),
    # direkt aus ifcopenshell.geom mit USE_WORLD_COORDS=True.
    dreiecke: List[tuple]


def lade_bauteile(ifc_file_path: str) -> Iterable[IfcBauteilGeometrie]:
    """Lade alle RELEVANT_IFC_CLASSES-Elemente inkl. Weltkoordinaten-Mesh.

    TODO (Etappe 3):
        import ifcopenshell
        import ifcopenshell.geom

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        ifc_file = ifcopenshell.open(ifc_file_path)
        for ifc_class in RELEVANT_IFC_CLASSES:
            for element in ifc_file.by_type(ifc_class):
                shape = ifcopenshell.geom.create_shape(settings, element)
                # shape.geometry.verts / .faces -> Dreiecke aufbauen
                ...
    """

    raise NotImplementedError("Etappe 3: ifcopenshell-Anbindung")
