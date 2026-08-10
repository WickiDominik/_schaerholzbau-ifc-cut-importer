"""Parser for die Schnitt-Definition(en) in einem Cadwork Benutzerattribut.

Format (Text in einem Benutzerattribut, siehe app/config.py
SchnittDefinitionConfig.ATTRIBUTE_NUMBER) - EINE Definition pro Zeile,
dadurch koennen auf einem einzigen Element (z.B. einem Ausgabeelement)
beliebig viele Schnitte definiert werden:

    Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789.0,0;Richtung=0,1,0
    Name=Grundriss EG;Typ=horizontal;Ursprung=0,0,1000;Richtung=0,0,1

- Name: freier Text, wird als Schnittname verwendet (Zwischendatei-Name,
  Cadwork-Gruppe beim Import) - muss je Element eindeutig sein
- Typ: "horizontal" oder "vertikal"
- Ursprung: ein Punkt auf der Schnittebene, "x,y,z" in mm (Cadwork-Weltkoordinaten)
- Richtung: die Ebenennormale, "x,y,z" (muss nicht normiert sein)

Leere Zeilen werden ignoriert. Jede Zeile wird unabhaengig geparst - ein
Fehler in einer Zeile verhindert nicht das Einlesen der uebrigen Zeilen.

Diese Datei enthaelt keine Cadwork-Importe und kann daher sowohl vom
Cadwork-Plugin (ifc_schnitt_importer) als auch vom externen Generator-Tool
(generator_tool/) importiert werden - ein einziger Ort fuer das Format.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

Point3 = Tuple[float, float, float]

REQUIRED_KEYS = ("Name", "Typ", "Ursprung", "Richtung")
VALID_TYPEN = ("horizontal", "vertikal")


class SchnittDefinitionError(ValueError):
    """Raised when a Benutzerattribut text can't be parsed as a Schnitt-Definition."""


@dataclass
class SchnittDefinition:
    name: str
    typ: str  # "horizontal" | "vertikal"
    ursprung: Point3
    richtung: Point3
    source_element_id: Optional[int] = None

    def to_text(self) -> str:
        ux, uy, uz = self.ursprung
        rx, ry, rz = self.richtung
        return (
            f"Name={self.name};Typ={self.typ};"
            f"Ursprung={ux},{uy},{uz};Richtung={rx},{ry},{rz}"
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def parse_from_text(cls, text: str, source_element_id: Optional[int] = None) -> "SchnittDefinition":
        if not text or not text.strip():
            raise SchnittDefinitionError("Attribut ist leer")

        parts = {}
        for chunk in text.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "=" not in chunk:
                raise SchnittDefinitionError(f"Ungueltiges Feld ohne '=': {chunk!r}")
            key, _, value = chunk.partition("=")
            parts[key.strip()] = value.strip()

        missing = [k for k in REQUIRED_KEYS if k not in parts or not parts[k]]
        if missing:
            raise SchnittDefinitionError(f"Fehlende Felder: {', '.join(missing)}")

        name = parts["Name"]

        typ = parts["Typ"].strip().lower()
        if typ not in VALID_TYPEN:
            raise SchnittDefinitionError(f"Typ muss 'horizontal' oder 'vertikal' sein, nicht {parts['Typ']!r}")

        ursprung = cls._parse_point(parts["Ursprung"], "Ursprung")
        richtung = cls._parse_point(parts["Richtung"], "Richtung")

        if richtung[0] == 0 and richtung[1] == 0 and richtung[2] == 0:
            raise SchnittDefinitionError("Richtung darf kein Nullvektor sein")

        return cls(name=name, typ=typ, ursprung=ursprung, richtung=richtung, source_element_id=source_element_id)

    @classmethod
    def parse_multiple_from_text(
        cls, text: str, source_element_id: Optional[int] = None
    ) -> Tuple[List["SchnittDefinition"], List[str]]:
        """Parst mehrere Schnitt-Definitionen, eine pro Zeile.

        Rueckgabe: (erfolgreich geparste Definitionen, Fehlermeldungen je
        fehlerhafter Zeile inkl. Zeilennummer). Eine fehlerhafte Zeile
        blockiert nicht die uebrigen.
        """

        definitionen: List["SchnittDefinition"] = []
        fehler: List[str] = []

        if not text:
            return definitionen, fehler

        for line_number, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                definitionen.append(cls.parse_from_text(line, source_element_id=source_element_id))
            except SchnittDefinitionError as e:
                fehler.append(f"Zeile {line_number}: {e}")

        return definitionen, fehler

    @staticmethod
    def _parse_point(value: str, field_name: str) -> Point3:
        raw_parts = [p.strip() for p in value.split(",")]
        if len(raw_parts) != 3:
            raise SchnittDefinitionError(f"{field_name} braucht genau 3 Werte 'x,y,z', erhalten: {value!r}")
        try:
            return (float(raw_parts[0]), float(raw_parts[1]), float(raw_parts[2]))
        except ValueError as e:
            raise SchnittDefinitionError(f"{field_name} enthaelt keine gueltigen Zahlen: {value!r}") from e


@dataclass
class SchnittDefinitionFehler:
    element_id: int
    fehler: str


@dataclass
class SchnittDefinitionExport:
    """Result of scanning the Cadwork model for Schnitt-Definitionen."""

    definitionen: List[SchnittDefinition]
    fehler: List[SchnittDefinitionFehler]
