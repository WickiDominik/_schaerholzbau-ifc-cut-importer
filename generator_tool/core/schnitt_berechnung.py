"""Ebene x Bauteil-Mesh -> Schnittflaechen/-linien.

STATUS: Etappe 3 (Geruest). Kernaufgabe: fuer eine SchnittEbene (Ursprung
+ Normale, siehe shared/schnitt_format.py) und eine Liste von
IfcBauteilGeometrie (Dreiecksnetz, siehe ifc_reader.py) je Bauteil den
Schnitt mit der Ebene berechnen:

- Schnittlinien: jedes Dreieck, das die Ebene schneidet, liefert ein
  Liniensegment (Standard-Dreieck/Ebene-Schnitt, Vorzeichenwechsel der
  drei Eckpunkt-Abstaende zur Ebene pruefen).
- Schnittflaechen: die Liniensegmente eines Bauteils zu geschlossenen
  Polygonen verketten (Endpunkt-Matching mit Toleranz) - ergibt die
  gefuellte Schnittflaeche fuer die "Flaechen" des Importers.

ifcopenshell selbst bringt fuer sowas evtl. bereits Hilfsfunktionen
(z.B. ueber `ifcopenshell.util` oder externe clipping-Bibliotheken wie
`trimesh`/`shapely` fuer die Polygon-Verkettung) - bei der Umsetzung
pruefen statt komplett neu zu implementieren.
"""

from __future__ import annotations

from typing import Iterable, List

from generator_tool.core.ifc_reader import IfcBauteilGeometrie
from ifc_schnitt_importer.shared.schnitt_format import SchnittEbene, SchnittFlaeche, SchnittLinie


def berechne_schnitt(
    ebene: SchnittEbene,
    bauteile: Iterable[IfcBauteilGeometrie],
) -> tuple[List[SchnittFlaeche], List[SchnittLinie]]:
    """TODO (Etappe 3): Dreieck/Ebene-Schnitt je Bauteil, siehe Moduldoc."""

    raise NotImplementedError("Etappe 3: Schnittberechnung")
