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

`ifcopenshell` 0.8.5 laeuft nachweislich auf Python 3.13 (getestet
2026-08-10); unabhaengig davon, welche Python-Version Cadwork selbst
nutzt - `pip install ifcopenshell` in der venv zeigt die fuer die
jeweilige Python-Version tatsaechlich verfuegbare Version an.

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

Etappe 3 erledigt und gegen die mitgelieferte Demo-IFC end-to-end
verifiziert (siehe docs/konzept.md, "Etappe 3 - Validierung"). Bekannte
Luecke: IFC-Bauteil-Instanzen ohne eigene `Representation` (in der
Demo-IFC alle `IfcBeam`, ein Teil der `IfcColumn`) werden aktuell
uebersprungen statt ueber die Typ-Repraesentation aufgeloest.
