# Projektstruktur

Eigenstaendiges Cadwork-Plugin, bewusst an den Konventionen der
schaerholzbau Toolcenter (`_schaerholzbau-toolcenter`) ausgerichtet, damit
beide Plugins im selben Cadwork-Python-Prozess konfliktfrei nebeneinander
laufen und sich fuer Entwickler:innen identisch anfuehlen.

Das Tool besteht aus zwei getrennten Laufzeiten (siehe `docs/konzept.md`
fuer das Warum): dem eigentlichen Cadwork-Plugin (`ifc_schnitt_importer/`,
laeuft in Cadworks eingebettetem Python) und einem eigenstaendigen
externen Kommandozeilen-Tool (`generator_tool/`, eigene Python-Umgebung
mit `ifcopenshell`), das die IFC-Geometrie/Schnittberechnung uebernimmt,
weil Cadworks API dafuer kein geeignetes Werkzeug bietet.

```text
_schaerholzbau-ifc-schnitt-importer/
|- _schaerholzbau-ifc-schnitt-importer.py   Cadwork Entry Point
|- plugin_info.xml
|- docs/
|  |- konzept.md            Fachliches Konzept + Entscheidungen + Etappenplan
|  |- benutzerhandbuch.md   Kurzanleitung, im Fenster ueber "Hilfe" angezeigt
|  `- architecture.md       dieses Dokument
|- ifc_schnitt_importer/    Cadwork-Plugin, Namespace-Package
|  |- app/
|  |  |- bootstrap.py       sys.path / Dependency-Bootstrap
|  |  |- config.py          AppConfig, PathConfig, SchnittDefinitionConfig, ReferenceGeometryConfig
|  |  |- main.py            cadwork_menu() Einstiegspunkt
|  |  |- menu_controller.py Cadwork "simple menu" Dispatch (ein Menuepunkt)
|  |  `- main_window.py     EIN Fenster im Toolcenter-Stil: Schrittleiste, Schnitt-Tabelle, Generieren + Importieren
|  |- cadwork_api/          Duenne Wrapper um die Cadwork-Controller-Module
|  |  |- bim.py             bim_controller
|  |  |- elements.py        element_controller
|  |  |- geometry.py        geometry_controller
|  |  |- attributes.py      attribute_controller
|  |  |- project.py         utility_controller
|  |  `- visualization.py   visualization_controller
|  |- features/
|  |  |- schnitt_generator/ service.py: Benutzerattribute scannen -> schnitt_definitionen.json,
|  |  |                     generator_tool per Subprozess anstossen (kein window.py mehr - UI in app/main_window.py)
|  |  |- schnitt_importer/  service.py: .ifccut.json einlesen -> Flaechen/Linien im 3D, join_elements
|  |  |                    (kein window.py mehr - UI in app/main_window.py)
|  |  `- schnitt_workflow/  uebersicht.py: Status je Schnitt + naechster Schritt (reines Python, getestet)
|  |- shared/                Von Cadwork-Plugin UND generator_tool/ gemeinsam genutzt (reines Python)
|  |  |- schnitt_definition.py  Benutzerattribut-Textformat (Stufe 1 -> Stufe 2)
|  |  |- schnitt_format.py      Schnitt-Ergebnis-JSON (Stufe 2 -> Stufe 3)
|  |  |- logging.py             JSON-Fehlerlogging (pro Benutzer unter %APPDATA%)
|  |  |- local_settings.py      lokale UI-Einstellungen (pro Benutzer unter %APPDATA%)
|  |  |- user_paths.py          %APPDATA%\schaerholzbau\ifc_schnitt_importer\{settings,logs}
|  |  |- window_utils.py        Tk-Root/Toplevel-Handling (Shell vs. API)
|  |  |- theme.py               Farben/Schriften/Knopfarten (Kopie aus dem Toolcenter)
|  |  |- window_geometry.py     Position neben Cadwork, DPI (Kopie aus dem Toolcenter)
|  |  |- tool_window.py         Fensterbasis im Toolcenter-Stil (Kopfband, Statuszeile, Fusszeile)
|  |  |- help_window.py         Hilfefenster (zeigt docs/benutzerhandbuch.md)
|  |  `- dependencies/          Bootstrap-Erweiterungspunkt (aktuell keine externen Pakete noetig)
|  |- resources/icons/
|  |- settings/             nur Rueckfall, falls %APPDATA% nicht beschreibbar ist
|  |- logs/                 nur Rueckfall, falls %APPDATA% nicht beschreibbar ist
|  `- tests/
|     |- manual/            gegen die echte Cadwork-API laufende Testskripte
|     `- unit/              reine Python-Tests (Formate, Services mit gefaelschter Cadwork-API)
`- generator_tool/           Eigenstaendiges CLI-Tool, eigene Python-Umgebung (siehe README.md)
   |- schnitt_generator.py   CLI-Einstiegspunkt
   |- requirements.txt       ifcopenshell
   |- README.md              Setup + Ausfuehrung
   `- core/
      |- ifc_reader.py           IFC laden (ifcopenshell), Etappe 3
      |- schnitt_berechnung.py   Ebenen-Schnitt-Geometrie, Etappe 3
      `- schnitt_definitionen.py Bruecken-Datei einlesen
```

## Import-Regeln

Wie im Toolcenter: alle internen Imports namespaced unter
`ifc_schnitt_importer.*`, keine generischen Top-Level-Module (`config`,
`ui`, `utils`, ...). Direkte Cadwork-Controller-Imports (`import
bim_controller`, `import element_controller`, ...) sind ausschliesslich
in `ifc_schnitt_importer/cadwork_api/*` erlaubt.

## Validierung

```powershell
python -m compileall ifc_schnitt_importer
python -m py_compile _schaerholzbau-ifc-schnitt-importer.py

# Unit-Tests (laufen ohne Cadwork und ohne ifcopenshell)
python generator_tool/tests/test_schnitt_berechnung.py
python ifc_schnitt_importer/tests/unit/test_shared_formate.py
python ifc_schnitt_importer/tests/unit/test_services.py
python ifc_schnitt_importer/tests/unit/test_uebersicht.py
```

Alle Testdateien laufen auch mit `pytest`, falls installiert.

(Ausserhalb von Cadwork schlagen Importe von `bim_controller` etc.
erwartungsgemaess fehl - diese sind nur im eingebetteten Cadwork-Python
verfuegbar. Fuer `python -m compileall` ist das unerheblich, da nur
Bytecode kompiliert, nicht ausgefuehrt wird.)

Siehe [konzept.md](konzept.md) fuer den fachlichen Hintergrund und den
Etappenplan.
