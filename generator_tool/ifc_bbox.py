"""Kleines Hilfsskript: Bounding-Box + Geschosshoehen einer IFC-Datei
ausgeben - fuer die Wahl sinnvoller Ursprung/Richtung-Werte in den
Schnitt-Definitionen (Benutzerattribute), OHNE Cadwork zu brauchen.

Nutzung (mit der generator_tool-venv, siehe README.md):

    .venv\\Scripts\\python ifc_bbox.py --ifc "C:\\Pfad\\zur\\Datei.ifc"

Gibt die Bounding-Box (mm, Cadwork-Konvention) der Bauteile aus
core.ifc_reader.RELEVANT_IFC_CLASSES sowie alle IfcBuildingStorey-Namen
und -Hoehen aus. Beispiel fuer die Weiterverwendung: eine horizontale
Schnitt-Definition auf "1m ueber Erdgeschoss" waere dann
Ursprung=0,0,<EG-Elevation + 1000>;Richtung=0,0,1 - eine vertikale
z.B. in der X-Mitte der Bounding-Box.
"""

from __future__ import annotations

import argparse
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PROJECT_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from generator_tool.core.ifc_reader import RELEVANT_IFC_CLASSES, lade_bauteile


def main():
    parser = argparse.ArgumentParser(description="IFC Bounding-Box + Geschosse ausgeben")
    parser.add_argument("--ifc", required=True, help="Pfad zur IFC-Datei")
    args = parser.parse_args()

    import ifcopenshell
    import ifcopenshell.util.unit as ifc_unit

    ifc_file = ifcopenshell.open(args.ifc)
    scale = ifc_unit.calculate_unit_scale(ifc_file) * 1000.0

    print(f"Datei: {args.ifc}")
    print(f"Schema: {ifc_file.schema}")
    print()

    print("Geschosse (IfcBuildingStorey):")
    for storey in ifc_file.by_type("IfcBuildingStorey"):
        elevation_mm = (storey.Elevation or 0.0) * scale
        print(f"  {storey.Name!r}: Elevation = {elevation_mm:.1f} mm")
    print()

    print(f"Berechne Bounding-Box aus {', '.join(RELEVANT_IFC_CLASSES)} ...")
    xs, ys, zs = [], [], []
    n_bauteile = 0
    for bauteil in lade_bauteile(args.ifc):
        n_bauteile += 1
        for triangle in bauteil.dreiecke:
            for x, y, z in triangle:
                xs.append(x)
                ys.append(y)
                zs.append(z)

    if not xs:
        print("Keine Geometrie gefunden - Bounding-Box nicht berechenbar.")
        return

    print(f"{n_bauteile} Bauteile ausgewertet.")
    print()
    print(f"X: {min(xs):.1f} .. {max(xs):.1f} mm  (Mitte: {(min(xs)+max(xs))/2:.1f})")
    print(f"Y: {min(ys):.1f} .. {max(ys):.1f} mm  (Mitte: {(min(ys)+max(ys))/2:.1f})")
    print(f"Z: {min(zs):.1f} .. {max(zs):.1f} mm  (Mitte: {(min(zs)+max(zs))/2:.1f})")
    print()
    print("Beispiel-Schnitt-Definitionen (bitte Namen/Werte anpassen):")
    mid_x = (min(xs) + max(xs)) / 2
    mid_y = (min(ys) + max(ys)) / 2
    print(f"  Name=Schnitt Mitte X;Typ=vertikal;Ursprung={mid_x:.0f},0,0;Richtung=1,0,0")
    print(f"  Name=Schnitt Mitte Y;Typ=vertikal;Ursprung=0,{mid_y:.0f},0;Richtung=0,1,0")


if __name__ == "__main__":
    main()
