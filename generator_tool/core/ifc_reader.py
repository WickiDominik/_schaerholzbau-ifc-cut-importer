"""IFC laden via ifcopenshell.

Laedt alle raeumlich relevanten Bauteile (RELEVANT_IFC_CLASSES) mit ihrer
bereits durch ifcopenshell aufgeloesten Weltkoordinaten-Geometrie -
inklusive automatisch abgezogener IfcOpeningElement-Aussparungen (Teil
von ifcopenshell.geom's Standardverhalten beim Erzeugen der Shape eines
Elements, das IfcRelVoidsElement-Beziehungen hat).

Koordinaten werden nach Millimeter skaliert (Cadwork-Konvention), unabh-
aengig davon, in welcher Laengeneinheit die IFC-Datei selbst deklariert
ist (ermittelt ueber ifcopenshell.util.unit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Tuple

Point3 = Tuple[float, float, float]
Triangle = Tuple[Point3, Point3, Point3]

# Bauteilklassen, die in die Schnittberechnung einfliessen. Bewusst OHNE
# Tueren/Fenster (nur Rohbau-relevant fuer den Holzbau-Vergleich) - bei
# Bedarf spaeter mit dem Anwender erweitern/einschraenken.
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
    # Weltkoordinaten-Dreiecksnetz (mm), Liste von (p0, p1, p2)-Tripeln.
    dreiecke: List[Triangle] = field(default_factory=list)


def _mm_scale_factor(ifc_file) -> float:
    """Skalierungsfaktor von der Datei-Laengeneinheit zu Millimetern."""

    import ifcopenshell.util.unit as ifc_unit

    # calculate_unit_scale liefert den Faktor zu SI-Metern.
    meters_per_unit = ifc_unit.calculate_unit_scale(ifc_file)
    return meters_per_unit * 1000.0


def lade_bauteile(ifc_file_path: str, ifc_classes: Tuple[str, ...] = RELEVANT_IFC_CLASSES) -> Iterator[IfcBauteilGeometrie]:
    """Lade alle `ifc_classes`-Elemente inkl. Weltkoordinaten-Mesh (mm)."""

    import ifcopenshell
    import ifcopenshell.geom

    ifc_file = ifcopenshell.open(ifc_file_path)
    scale = _mm_scale_factor(ifc_file)

    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    # Elemente koennen ueber mehrere IFC-Klassen mehrfach erfasst werden
    # (z.B. IfcWall UND IfcWallStandardCase existieren in derselben Datei
    # praktisch nie fuer dasselbe Element, aber zur Sicherheit ueber GUID
    # deduplizieren).
    seen_guids = set()

    for ifc_class in ifc_classes:
        for element in ifc_file.by_type(ifc_class):
            if element.GlobalId in seen_guids:
                continue

            if element.Representation is None:
                # Bekannte Luecke (siehe docs/konzept.md, Etappe 3): manche
                # Archicad-IFC2X3-Exporte geben Bauteil-Instanzen (in der
                # Demo-IFC z.B. ALLE IfcBeam und ein Teil der IfcColumn)
                # keine eigene Representation - die Geometrie liegt dann
                # (falls ueberhaupt) nur am IfcTypeObject. Wird hier noch
                # nicht aufgeloest, Element wird uebersprungen.
                print(f"[ifc_reader] {ifc_class} {element.GlobalId} hat keine eigene Representation - uebersprungen")
                continue

            try:
                shape = ifcopenshell.geom.create_shape(settings, element)
            except RuntimeError as e:
                print(f"[ifc_reader] Geometrie fuer {ifc_class} {element.GlobalId} nicht erzeugbar: {e}")
                continue

            seen_guids.add(element.GlobalId)

            verts = shape.geometry.verts  # flach: x0,y0,z0,x1,y1,z1,...
            faces = shape.geometry.faces  # flach: i0,i1,i2, i0,i1,i2, ... (bereits trianguliert)

            points = [
                (verts[i] * scale, verts[i + 1] * scale, verts[i + 2] * scale)
                for i in range(0, len(verts), 3)
            ]

            dreiecke: List[Triangle] = []
            for i in range(0, len(faces), 3):
                dreiecke.append((points[faces[i]], points[faces[i + 1]], points[faces[i + 2]]))

            yield IfcBauteilGeometrie(ifc_guid=element.GlobalId, ifc_type=ifc_class, dreiecke=dreiecke)
