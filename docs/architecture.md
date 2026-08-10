# Projektstruktur

Eigenstaendiges Cadwork-Plugin, bewusst an den Konventionen der
schaerholzbau Toolcenter (`_schaerholzbau-toolcenter`) ausgerichtet, damit
beide Plugins im selben Cadwork-Python-Prozess konfliktfrei nebeneinander
laufen und sich fuer Entwickler:innen identisch anfuehlen.

```text
_schaerholzbau-ifc-schnitt-importer/
|- _schaerholzbau-ifc-schnitt-importer.py   Cadwork Entry Point
|- plugin_info.xml
|- docs/
|  |- konzept.md            Fachliches Konzept + Entscheidungen + Etappenplan
|  `- architecture.md       dieses Dokument
`- ifc_schnitt_importer/    Namespace-Package (keine generischen Top-Level-Module)
   |- app/
   |  |- bootstrap.py       sys.path / Dependency-Bootstrap
   |  |- config.py          AppConfig, PathConfig, ReferenceGeometryConfig, UITextConfig
   |  |- main.py            cadwork_menu() Einstiegspunkt
   |  `- menu_controller.py Cadwork "simple menu" Dispatch
   |- cadwork_api/          Duenne Wrapper um die Cadwork-Controller-Module
   |  |- bim.py             bim_controller (IFC-Import, Storeys)
   |  |- elements.py        element_controller
   |  |- geometry.py        geometry_controller
   |  |- attributes.py      attribute_controller
   |  |- project.py         utility_controller
   |  `- visualization.py   visualization_controller
   |- features/
   |  |- schnitt_generator/ IFC laden + Schnitte berechnen (window/service)
   |  `- schnitt_importer/  Flaechen/Linien im 3D erzeugen (window/service)
   |- shared/
   |  |- schnitt_format.py  Austauschformat Generator <-> Importer (JSON)
   |  |- logging.py         JSON-Fehlerlogging
   |  |- window_utils.py    Tk-Root/Toplevel-Handling (Shell vs. API)
   |  `- dependencies/      Bootstrap-Erweiterungspunkt (aktuell keine externen Pakete noetig)
   |- resources/icons/
   |- settings/
   |- logs/
   `- tests/
      |- manual/            gegen die echte Cadwork-API laufende Testskripte
      `- unit/
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
```

(Ausserhalb von Cadwork schlagen Importe von `bim_controller` etc.
erwartungsgemaess fehl - diese sind nur im eingebetteten Cadwork-Python
verfuegbar. Fuer `python -m compileall` ist das unerheblich, da nur
Bytecode kompiliert, nicht ausgefuehrt wird.)

Siehe [konzept.md](konzept.md) fuer den fachlichen Hintergrund und den
Etappenplan.
