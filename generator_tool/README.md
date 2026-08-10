# IFC Schnitt Generator (externes Tool)

Laeuft **ausserhalb von Cadwork**, in einer eigenen Python-Umgebung. Grund:
Cadworks eigene API kann IFC-Elemente nicht sauber mit einer Ebene
schneiden (`element_controller.cut_element_with_plane` mutiert ein echtes
Cadwork-Element und funktioniert nicht auf den leichten "Exchange
Objects" des IFC-Imports - siehe docs/konzept.md, Etappe-0-Ergebnisse).
`ifcopenshell` (mit seinem OpenCASCADE-Geometriekern) ist fuer genau diese
Aufgabe gebaut und laeuft hier unabhaengig von Cadworks eigener
Python-Version (3.12/3.14).

## Setup (einmalig)

```powershell
cd generator_tool
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

`ifcopenshell` unterstuetzt aktuell Python 3.9-3.12 (Stand 2026-08-10,
siehe docs/konzept.md) - bitte eine venv mit einer dieser Versionen
verwenden, unabhaengig davon, welche Python-Version Cadwork selbst nutzt.

## Ausfuehren

```powershell
.venv\Scripts\python schnitt_generator.py ^
    --ifc "C:\Pfad\zur\Archicad-Export.ifc" ^
    --definitionen "<Projekt>\IFC_Schnitte\schnitt_definitionen.json" ^
    --output "<Projekt>\IFC_Schnitte"
```

- `--definitionen`: wird vom Cadwork-Plugin (Menuepunkt "IFC Schnitt
  Generator") aus den Benutzerattributen der markierten Elemente erzeugt.
- `--output`: derselbe `IFC_Schnitte`-Ordner, aus dem das Cadwork-Plugin
  ("IFC Schnitt Importer") die Ergebnisse anschliessend einliest.

Pro Schnitt-Definition entsteht eine Datei
`<projekt>_<schnittname>.ifccut.json` (Format: siehe
`ifc_schnitt_importer/shared/schnitt_format.py` - dieses Tool importiert
dasselbe Modul, es gibt nur EIN Format).

## Status

Etappe 3 (noch offen): `core/ifc_reader.py` und
`core/schnitt_berechnung.py` sind Geruest/TODO. Die eigentliche
Ebenen-Schnitt-Geometrie (IFC-Solid x Schnittebene -> Polygon/Linien)
folgt als naechster Programmierschritt.
