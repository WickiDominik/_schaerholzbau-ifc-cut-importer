"""Read the Cadwork-exported schnitt_definitionen.json bridging file.

Reuses ifc_schnitt_importer.shared.schnitt_definition (pure Python, no
Cadwork-only imports) so both halves of the tool share one Schnitt-
Definition dataclass instead of duplicating the parsing logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from ifc_schnitt_importer.shared.schnitt_definition import SchnittDefinition


@dataclass
class SchnittDefinitionenDatei:
    projekt_nummer: str
    quelle_3d_datei: str
    definitionen: List[SchnittDefinition]


def load_schnitt_definitionen(file_path: str) -> SchnittDefinitionenDatei:
    with open(file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    definitionen = [SchnittDefinition(**d) for d in payload.get("definitionen", [])]
    return SchnittDefinitionenDatei(
        projekt_nummer=payload.get("projekt_nummer", ""),
        quelle_3d_datei=payload.get("quelle_3d_datei", ""),
        definitionen=definitionen,
    )
