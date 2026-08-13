# Holzbau IFC Schnitt Importer

Eigenständiges Cadwork-Plugin für die Schärholzbau Holzbau-GU-Planung:
generiert Grundriss- und Gebäudeschnitte aus einer vom Architekten (GU)
gelieferten IFC-Datei und importiert die Ergebnisse lagerichtig als
Referenz-Flächen und -Linien ins 3D-Modell.

## Arbeitsablauf

```
1. GU exportiert IFC aus Archicad/Vectorworks/...
2. Holzbau-Planung definiert Schnitte als Benutzerattribute in Cadwork
3. "IFC Schnitt Generator" (im Cadwork-Fenster): IFC wählen, generieren
4. "IFC Schnitt Importer" (gleiches Fenster): Ergebnis ins 3D importieren
```

Beide Schritte laufen in **einem gemeinsamen Fenster** im Cadwork-Menü,
mit Fortschrittsanzeige. Details siehe [`docs/konzept.md`](docs/konzept.md).

## Warum zwei Laufzeiten

Das Tool besteht aus zwei getrennten Teilen:

- **`ifc_schnitt_importer/`** – das eigentliche Cadwork-Plugin, läuft in
  Cadworks eingebettetem Python.
- **`generator_tool/`** – ein eigenständiges Kommandozeilen-Tool mit
  eigener Python-Umgebung (`ifcopenshell`), das die IFC-Geometrie liest
  und die Schnittebenen berechnet. Läuft **außerhalb** von Cadwork, weil
  Cadworks eigene API dafür kein geeignetes Werkzeug bietet (siehe
  [`docs/konzept.md`](docs/konzept.md), Abschnitt „Warum die
  Schnittberechnung außerhalb von Cadwork passiert").

Der Cadwork-Teil stößt den externen Teil bei Bedarf automatisch als
Subprozess an – für die tägliche Nutzung reicht das Cadwork-Fenster,
ein Terminal wird nicht gebraucht.

## Einmaliges Setup

Cadwork-seitig ist keine Installation nötig (Plugin einfach in Cadworks
Plugin-Verzeichnis auschecken/kopieren). Für den externen Generator-Teil
einmalig eine eigene Python-Umgebung einrichten:

```bash
cd generator_tool
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Ohne diese venv zeigt der "Schnitte generieren"-Button im Cadwork-Fenster
eine Anleitung statt eines kryptischen Fehlers.

## Schnitte definieren

Jeder Schnitt wird als strukturierter Text in einem Cadwork-
Benutzerattribut hinterlegt (ein Attribut pro Schnitt, Nummern 20–29,
siehe `ifc_schnitt_importer/app/config.py` → `SchnittDefinitionConfig`):

```text
Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789.0,0;Richtung=0,1,0
```

- `Name`: Schnittname (wird zu Dateiname, Cadwork-Gruppe/BG)
- `Typ`: `horizontal` oder `vertikal`
- `Ursprung`: ein Punkt auf der Schnittebene, `x,y,z` in mm
- `Richtung`: die Ebenennormale, `x,y,z`

Zur Ermittlung sinnvoller Koordinaten für ein konkretes Projekt:

```bash
generator_tool\.venv\Scripts\python generator_tool\ifc_bbox.py --ifc "C:\Pfad\zur\Datei.ifc"
```

gibt Bounding-Box und Geschosshöhen der IFC-Datei aus.

## Dokumentation

- [`docs/konzept.md`](docs/konzept.md) – fachliches Konzept, alle
  Entscheidungen, Etappenplan, ausführliches Livetest-Log
- [`docs/architecture.md`](docs/architecture.md) – Projektstruktur
- [`generator_tool/README.md`](generator_tool/README.md) – Setup/Details
  zum externen Tool

## Status

In aktiver Entwicklung, mehrfach gegen reale Projekt-IFC-Dateien
getestet (siehe `docs/konzept.md`). Internes Tool für die Schärholzbau
AG – kein öffentliches Release.
