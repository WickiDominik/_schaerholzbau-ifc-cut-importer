"""Unit-Test fuer die Ebenen-Schnitt-Geometrie, ohne ifcopenshell/Cadwork.

Ausfuehren:
    python generator_tool/tests/test_schnitt_berechnung.py
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from generator_tool.core.ifc_reader import IfcBauteilGeometrie
from generator_tool.core.schnitt_berechnung import berechne_schnitt
from ifc_schnitt_importer.shared.schnitt_format import SchnittEbene


def _wuerfel_dreiecke(size=1000.0):
    """Achsparalleler Wuerfel [0,size]^3 als 12 Dreiecke (2 je Seite)."""

    v000 = (0, 0, 0)
    v100 = (size, 0, 0)
    v110 = (size, size, 0)
    v010 = (0, size, 0)
    v001 = (0, 0, size)
    v101 = (size, 0, size)
    v111 = (size, size, size)
    v011 = (0, size, size)

    quads = [
        (v000, v100, v110, v010),  # unten
        (v001, v101, v111, v011),  # oben
        (v000, v100, v101, v001),  # vorne
        (v010, v110, v111, v011),  # hinten
        (v000, v010, v011, v001),  # links
        (v100, v110, v111, v101),  # rechts
    ]

    dreiecke = []
    for a, b, c, d in quads:
        dreiecke.append((a, b, c))
        dreiecke.append((a, c, d))
    return dreiecke


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def test_horizontaler_schnitt_durch_wuerfel_liefert_ein_quadrat():
    size = 1000.0
    bauteil = IfcBauteilGeometrie(ifc_guid="TEST-GUID", ifc_type="IfcWall", dreiecke=_wuerfel_dreiecke(size))
    ebene = SchnittEbene(origin=[0, 0, size / 2], normal=[0, 0, 1])

    flaechen, linien = berechne_schnitt(ebene, [bauteil])

    _assert(len(flaechen) == 1, f"genau 1 geschlossene Flaeche erwartet, erhalten {len(flaechen)}")
    _assert(len(flaechen[0].vertices) == 4, f"Quadrat mit 4 Ecken erwartet, erhalten {len(flaechen[0].vertices)}")
    for x, y, z in flaechen[0].vertices:
        _assert(abs(z - size / 2) < 1e-6, f"alle Punkte müssen auf z={size/2} liegen, war z={z}")
        _assert(-1e-6 <= x <= size + 1e-6 and -1e-6 <= y <= size + 1e-6, f"Punkt ausserhalb des Wuerfels: ({x},{y},{z})")

    # Geschlossene Ketten liefern keine eigenen Linien mehr - die Kontur
    # wird beim Import direkt aus den Flaechen-Eckpunkten erzeugt.
    _assert(len(linien) == 0, f"keine separaten Linien fuer eine geschlossene Flaeche erwartet, erhalten {len(linien)}")

    flaeche_fuss = _polygon_area_xy(flaechen[0].vertices)
    _assert(abs(flaeche_fuss - size * size) < 1e-3, f"Flaeche sollte {size*size} sein, war {flaeche_fuss}")


def test_diagonaler_schnitt_liefert_geschlossenes_sechseck():
    size = 1000.0
    bauteil = IfcBauteilGeometrie(ifc_guid="TEST-GUID-2", ifc_type="IfcColumn", dreiecke=_wuerfel_dreiecke(size))
    # Ebene durch die Wuerfelmitte, schraeg -> klassischer Sechseck-Schnitt
    ebene = SchnittEbene(origin=[size / 2, size / 2, size / 2], normal=[1, 1, 1])

    flaechen, linien = berechne_schnitt(ebene, [bauteil])

    _assert(len(flaechen) == 1, f"genau 1 geschlossene Flaeche erwartet, erhalten {len(flaechen)}")
    _assert(len(flaechen[0].vertices) == 6, f"Sechseck erwartet, erhalten {len(flaechen[0].vertices)} Ecken")


def test_ebene_ausserhalb_des_wuerfels_liefert_nichts():
    size = 1000.0
    bauteil = IfcBauteilGeometrie(ifc_guid="TEST-GUID-3", ifc_type="IfcSlab", dreiecke=_wuerfel_dreiecke(size))
    ebene = SchnittEbene(origin=[0, 0, size * 2], normal=[0, 0, 1])

    flaechen, linien = berechne_schnitt(ebene, [bauteil])

    _assert(len(flaechen) == 0, "keine Flaeche erwartet, Ebene liegt ausserhalb des Wuerfels")
    _assert(len(linien) == 0, "keine Linie erwartet, Ebene liegt ausserhalb des Wuerfels")


def _polygon_area_xy(vertices):
    """Shoelace-Formel (funktioniert hier, da der Testring in der XY-Ebene liegt)."""

    area = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1, _ = vertices[i]
        x2, y2, _ = vertices[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def main():
    tests = [
        test_horizontaler_schnitt_durch_wuerfel_liefert_ein_quadrat,
        test_diagonaler_schnitt_liefert_geschlossenes_sechseck,
        test_ebene_ausserhalb_des_wuerfels_liefert_nichts,
    ]
    for test in tests:
        print(f"--- {test.__name__} ---")
        test()
    print("\nAlle Tests erfolgreich.")


if __name__ == "__main__":
    main()
