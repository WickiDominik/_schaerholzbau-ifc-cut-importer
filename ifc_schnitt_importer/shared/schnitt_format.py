"""Shared exchange format between Schnitt-Generator and Schnitt-Importer.

This is the contract between the two plugin stages (see docs/konzept.md):
the Generator writes one JSON file per Schnitt, the Importer only ever
reads this format. Keeping it in `shared/` (rather than inside either
feature package) makes that contract explicit and prevents the Importer
from reaching into the Generator's internals.

Coordinates are plain [x, y, z] lists in Cadwork world coordinates (mm),
taken 1:1 from the IFC-derived geometry per the current project decision
(no coordinate calibration step yet - see docs/konzept.md, offene Punkte).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Literal, Optional

FORMAT_VERSION = 1

SchnittTyp = Literal["horizontal", "vertikal"]

Point3 = List[float]  # [x, y, z] in mm


@dataclass
class SchnittEbene:
    """Cutting plane derived from a Cadwork Ausgabeelement / Achse.

    origin: a point on the plane (mm, Cadwork world coordinates)
    normal: plane normal, unit vector
    source_element_id: the Cadwork element (Ausgabeelement/Achse) the
        plane was taken from, kept for traceability and re-generation.
    """

    origin: Point3
    normal: Point3
    source_element_id: Optional[int] = None


@dataclass
class SchnittFlaeche:
    """One filled cross-section polygon (a cut face of an IFC element)."""

    vertices: List[Point3]
    ifc_element_type: str = ""
    ifc_guid: str = ""


@dataclass
class SchnittLinie:
    """One outline/edge segment of a cross-section."""

    start: Point3
    end: Point3
    ifc_element_type: str = ""
    ifc_guid: str = ""


@dataclass
class SchnittErgebnis:
    """Complete result for one Schnitt, as written by the Generator."""

    format_version: int
    schnitt_name: str
    schnitt_typ: SchnittTyp
    projekt_nummer: str
    quelle_ifc_datei: str
    erzeugt_am: str
    ebene: SchnittEbene
    flaechen: List[SchnittFlaeche] = field(default_factory=list)
    linien: List[SchnittLinie] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> "SchnittErgebnis":
        data = json.loads(text)
        data["ebene"] = SchnittEbene(**data["ebene"])
        data["flaechen"] = [SchnittFlaeche(**f) for f in data.get("flaechen", [])]
        data["linien"] = [SchnittLinie(**l) for l in data.get("linien", [])]
        return SchnittErgebnis(**data)


def save_schnitt_ergebnis(ergebnis: SchnittErgebnis, file_path: str) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(ergebnis.to_json())


def load_schnitt_ergebnis(file_path: str) -> SchnittErgebnis:
    with open(file_path, "r", encoding="utf-8") as f:
        return SchnittErgebnis.from_json(f.read())
