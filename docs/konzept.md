# Holzbau IFC Schnitt Importer - Konzept

Stand: 2026-08-10. Dieses Dokument haelt fest, was mit dem Auftraggeber
(Dominik Wicki, Schaerholzbau) gemeinsam definiert wurde, bevor die
Programmierarbeiten etappenweise begonnen haben.

## Ziel / Anwendungsfall

Die Holzbau-GU-Planungsabteilung erhaelt vom Architekten (GU) periodisch
eine aktualisierte IFC-Datei. Bisher muessen Grundrisse/Schnitte des
Architekturmodells manuell mit dem Holzbaumodell verglichen werden. Das
Tool automatisiert das:

```
1. GU exportiert IFC aus Archicad
2. "Holzbau IFC Schnitt Generator" starten
3. Tool laedt die IFC und generiert Schnitte nach Definition in Cadwork
4. "Schnitt Importer" importiert die Schnitte als Flaechen und Linien
   an die IFC-Originalposition ins 3D
```

Die importierte Geometrie dient als **Konstruktionsgrundlage fuer die
Ausfuehrungsplanung** (praezise, reproduzierbare Referenzgeometrie -
kein Wegwerf-Vergleichsbild).

## Mit dem Nutzer geklaerte Entscheidungen

| Frage | Entscheidung |
|---|---|
| Was ist ein "Schnitt"? | Beides: horizontale (Geschoss-/Grundriss-) und vertikale (Bauschnitt-) Ebenen, konfigurierbar |
| Woher kommt die Schnittlage? | Urspruenglich: abgeleitet aus bestehenden Cadwork-Ausgabeelementen. Nach Etappe-0-Spike geaendert auf: manuell als Benutzerattribut, siehe unten |
| Zweck der importierten Fl./Lin. | Konstruktionsgrundlage fuer die Ausfuehrungsplanung - praezise, reproduzierbar, klar von echten Bauteilen getrennt |
| Koordinatensystem | Vorerst 1:1 Uebernahme (IFC- und Cadwork-Modell teilen sich denselben Nullpunkt); spaetere Kalibrierung als Erweiterung offen |
| Projektstruktur | Eigenstaendiges Cadwork-Plugin (eigener Ordner `_schaerholzbau-ifc-schnitt-importer`, eigene `plugin_info.xml`), ein Plugin mit zwei Menuepunkten (Generator + Importer) |

## Etappe 0 - Ergebnisse (API-Spike, 2026-08-10)

Der Anwender hat `ifc_schnitt_importer/tests/manual/api_spike.py` gegen
die echte Cadwork-API laufen lassen. Ergebnisse und daraus folgende
Architektur-Entscheidungen:

1. **`bim_controller.import_ifc_return_exchange_objects` importiert
   lagerichtig.** Bestaetigt die 1:1-Koordinatenannahme (siehe oben).
2. **Es gibt (noch) keine API, um die Ebene eines Ausgabeelements
   auszulesen.** Workaround: die Schnitt-Definition (Name, Typ, Ursprung,
   Richtung) wird stattdessen manuell als strukturierter Text in einem
   Cadwork-Benutzerattribut hinterlegt - siehe Abschnitt
   "Schnitt-Definition (Benutzerattribut)" unten.
3. **`element_controller.cut_element_with_plane` ist fuer diesen
   Anwendungsfall ungeeignet.** Es schneidet ein *echtes* Cadwork-Element
   entlang Punkt+Normale und liefert die ID des abgeschnittenen Teils
   zurueck - funktioniert nicht mit den leichten Exchange Objects des
   IFC-Imports. **Konsequenz: die Schnittberechnung (IFC-Geometrie x
   Ebene) findet nicht mehr in Cadwork statt**, sondern in einem
   eigenstaendigen externen Tool (`generator_tool/`, eigenes Python +
   `ifcopenshell`, siehe "Warum ausserhalb von Cadwork" unten).
4. **Cadwork uebernimmt IFC-Types, -Storeys und -Buildings korrekt** beim
   Import. Aktuell nicht mehr im kritischen Pfad (siehe Punkt 3), evtl.
   spaeter nuetzlich fuer Building/Storey-Zuordnung der importierten
   Referenzgeometrie.

## Warum die Schnittberechnung ausserhalb von Cadwork passiert

Aus Punkt 3 oben: Cadworks eigene API bietet kein Werkzeug, um ein
IFC-Bauteil sauber mit einer Ebene zu schneiden und ein 2D-Schnittprofil
(Polygon/Linien) zurueckzubekommen. Gleichzeitig loest das ein zweites
Problem: Cadwork SP2026 laeuft auf Python 3.14 (siehe Toolcenter
`docs/architecture.md`), und `ifcopenshell` bietet aktuell keine Wheels
fuer Python 3.13/3.14 (gepruefte PyPI-Metadaten, Stand 2026-08-10) - eine
Loesung *innerhalb* von Cadworks eingebettetem Python waere fuer SP2026
also ohnehin nicht moeglich gewesen.

**Deshalb:** die eigentliche IFC-Geometrie-Verarbeitung (`ifcopenshell`,
Ebenen-Schnitt) laeuft in `generator_tool/` als eigenstaendiges
Kommandozeilen-Tool mit eigener, von Cadwork komplett unabhaengiger
Python-Umgebung (z.B. 3.12, siehe `generator_tool/README.md`). Cadworks
`bim_controller.import_ifc_return_exchange_objects` (Punkt 1 oben) wird
dafuer nicht mehr gebraucht; die bestaetigte 1:1-Lagerichtigkeit ist aber
weiterhin relevant, weil sie zeigt, dass Cadworks Weltkoordinaten mit den
rohen IFC-Koordinaten uebereinstimmen - `ifcopenshell`-Geometrie kann also
direkt (ohne Cadwork als Zwischenschritt) uebernommen werden.

Quelle Cadwork-API: [docs.cadwork.com - bim_controller](https://docs.cadwork.com/projects/cwapi3dpython/en/latest/documentation/bim_controller/)
(abgerufen 2026-08-10).

## Schnitt-Definition (Benutzerattribut)

Da die Ausgabeelement-Ebene nicht per API lesbar ist, definiert der
Anwender die Schnitt-Definition manuell in EINEM Cadwork-Benutzerattribut
(Nummer siehe `app/config.py` -> `SchnittDefinitionConfig`, aktuell 20)
auf dem Ausgabeelement (oder jedem anderen Referenzelement) als
strukturierter Text:

```text
Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789.0,0;Richtung=0,1,0
```

- `Name`: Schnittname (Zwischendatei-Name, Cadwork-Gruppe beim Import)
- `Typ`: `horizontal` oder `vertikal`
- `Ursprung`: ein Punkt auf der Schnittebene, `x,y,z` in mm (Cadwork-Weltkoordinaten)
- `Richtung`: die Ebenennormale, `x,y,z` (muss nicht normiert sein)

Parser + Validierung: [`ifc_schnitt_importer/shared/schnitt_definition.py`](../ifc_schnitt_importer/shared/schnitt_definition.py).
Das Cadwork-Plugin (Menuepunkt "IFC Schnitt Generator") scannt alle
Elemente, liest dieses Attribut, validiert es und schreibt eine
Bruecken-Datei `schnitt_definitionen.json` fuer das externe Tool.

## Architektur (3 Stufen)

Drei-Stufen-Workflow mit Zwischenformaten (Grundidee weiterhin analog
zum bestehenden `.cut3d`-Muster in `shb_toolcenter/features/cut_handling`
- einmal generieren, beliebig oft/von mehreren Personen importieren):

```
Stufe 1 (Cadwork-Plugin)         Stufe 2 (generator_tool/, extern)        Stufe 3 (Cadwork-Plugin)
---------------------------      -------------------------------------    -------------------------
"IFC Schnitt Generator":         schnitt_generator.py --ifc ... :         "IFC Schnitt Importer":
scannt Benutzerattribute         laedt IFC (ifcopenshell),                liest jede .ifccut.json,
-> schnitt_definitionen.json     berechnet je Definition den              erzeugt Flaechen
   (SchnittDefinition-Liste)     Ebenenschnitt (Etappe 3, offen)          (create_polygon_panel) +
                                 -> <projekt>_<name>.ifccut.json           Linien (create_line_points)
                                    (SchnittErgebnis)                      an IFC-Originalposition,
                                                                            eigene Gruppe
                                                                            "IFC-Referenz - <Name>"
```

Alle drei Stufen teilen sich denselben `IFC_Schnitte`-Ordner neben der
3D-Datei (`app/config.py` -> `PathConfig`).

## Datenformat

- **Schnitt-Definition** (Stufe 1 -> Stufe 2): [`ifc_schnitt_importer/shared/schnitt_definition.py`](../ifc_schnitt_importer/shared/schnitt_definition.py)
- **Schnitt-Ergebnis** (Stufe 2 -> Stufe 3): [`ifc_schnitt_importer/shared/schnitt_format.py`](../ifc_schnitt_importer/shared/schnitt_format.py)
  (`SchnittEbene`, `SchnittFlaeche`, `SchnittLinie`, `SchnittErgebnis`)

Beide Module sind reines Python ohne Cadwork-Importe und werden von
*beiden* Seiten (Cadwork-Plugin UND `generator_tool/`) importiert - ein
einziges, gemeinsames Format statt zweier Implementierungen.

## Etappe 3 - Validierung (2026-08-10)

Gegen die mitgelieferte Demo-IFC (`Archicad Demoprojekt Bürogebäude.ifc`,
IFC2X3, Erdgeschoss auf Elevation 0.0) end-to-end getestet:

- Horizontaler Schnitt (z=1000mm, "Grundriss EG +1.0m"): 17 Flaechen,
  68 Linien, alle Z-Koordinaten exakt 1000mm, X/Y-Bereich plausibel
  innerhalb der Wand-Bounding-Box.
- Vertikaler Schnitt (x=34750mm, "Schnitt Mitte X"): 26 Flaechen,
  108 Linien, alle X-Koordinaten exakt 34750mm, Z-Bereich -3900..13100mm
  passt zu den IFC-Geschoss-Elevationen (Fundament -5.3m bis
  Dachaufsicht 13.2m).
- Einheiten-Umrechnung (IFC-Datei in Meter -> mm) korrekt (Koordinaten
  stimmen mit der unabhaengig berechneten Wand-Bounding-Box in Metern
  ueberein, x1000).
- Laufzeit: ~4s fuer die ganze Demo-IFC (118 Bauteile) und 2 Schnitte.

**Bekannte Luecke:** In dieser Demo-IFC haben alle 24 `IfcBeam`- und
26 von 63 `IfcColumn`-Instanzen keine eigene `Representation` (nur das
`IfcTypeObject` traegt ggf. Geometrie, typisch fuer Archicad-Bibliotheks-
/GDL-Objekte in bestimmten Export-Einstellungen). `ifc_reader.py`
uebergeht diese Elemente aktuell mit einer Konsolen-Warnung, statt die
Typ-Repraesentation aufzuloesen. Waende, Decken und Fundamente sind
davon nicht betroffen (100% mit eigener Geometrie). Offen: pruefen, ob
sich das eher ueber Archicads IFC-Export-Einstellungen (Body-
Repraesentation fuer Traeger/Stuetzen aktivieren) oder ueber Aufloesen
der Typ-Repraesentation im Reader beheben laesst.

## Etappenplan

- [x] **Etappe 0**: API-Spike (Ergebnisse oben)
- [x] **Etappe 1**: Projekt-Grundgeruest, Plugin-Registrierung, Menu mit
      zwei Fenstern
- [x] **Etappe 2**: Cadwork-Plugin - Schnitt-Definitionen aus
      Benutzerattributen scannen + `schnitt_definitionen.json` exportieren
      (`SchnittGeneratorService.export_schnitt_definitionen`, UI in
      `features/schnitt_generator/window.py`)
- [x] **Etappe 3**: `generator_tool/` - `ifcopenshell`-Anbindung
      (`core/ifc_reader.py`) + Ebenen-Schnittberechnung
      (`core/schnitt_berechnung.py`, Dreieck/Ebene-Schnitt + Polylinien-
      Verkettung + Kollinearpunkt-Vereinfachung). Unit-getestet
      (`generator_tool/tests/test_schnitt_berechnung.py`, synthetischer
      Wuerfel) UND end-to-end gegen die mitgelieferte Demo-IFC verifiziert
      (siehe "Etappe 3 - Validierung" unten).
- [ ] **Etappe 4**: Cadwork-Plugin - Importer: Zwischendateien einlesen,
      Flaechen/Linien erzeugen, alten Import ersetzen
      (`SchnittImporterService.import_schnitt`)
- [ ] **Etappe 5**: UI/UX-Feinschliff (Fortschrittsanzeige, Fehlerbilder,
      Vorschau vor Import, Knopf um `generator_tool` direkt aus Cadwork
      anzustossen)
- [ ] **Etappe 6**: Test mit echten Projektdaten, Rollout
