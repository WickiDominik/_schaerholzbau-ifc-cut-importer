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
Anwender die Schnitt-Definition manuell in einem Cadwork-Benutzerattribut
auf dem Ausgabeelement (oder jedem anderen Referenzelement) als
strukturierter Text:

```text
Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789.0,0;Richtung=0,1,0
```

- `Name`: Schnittname (Zwischendatei-Name, Cadwork-Gruppe beim Import)
- `Typ`: `horizontal` oder `vertikal`
- `Ursprung`: ein Punkt auf der Schnittebene, `x,y,z` in mm (Cadwork-Weltkoordinaten)
- `Richtung`: die Ebenennormale, `x,y,z` (muss nicht normiert sein)

**Mehrere Schnitte auf einem Element:** Cadwork-Benutzerattribute sind
auf ca. 128 Zeichen begrenzt (live beobachtet - eine zweizeilige
Definition wurde bei genau 128 Zeichen abgeschnitten). Eine einzelne
Definition ist bereits ~70-90 Zeichen lang, mehrzeiliger Text in EINEM
Attribut skaliert also nicht. Stattdessen: mehrere Attribut-**Nummern**,
je eine Definition pro Nummer (`app/config.py` ->
`SchnittDefinitionConfig.attribute_numbers()`, Standard: 20-29, also bis
zu 10 Schnitte je Element - Attribut 20 = 1. Schnitt, 21 = 2. Schnitt,
usw.).

Parser + Validierung: [`ifc_schnitt_importer/shared/schnitt_definition.py`](../ifc_schnitt_importer/shared/schnitt_definition.py)
(`SchnittDefinition.parse_multiple_from_text` unterstuetzt zusaetzlich
weiterhin mehrere Zeilen *innerhalb* eines Attributs, falls kurze Namen
das zulassen - fuer den Regelfall aber: ein Attribut pro Schnitt).
Das Cadwork-Plugin (Menuepunkt "IFC Schnitt Generator") scannt alle
Elemente und alle konfigurierten Attribut-Nummern, validiert die Texte
und schreibt eine Bruecken-Datei `schnitt_definitionen.json` fuer das
externe Tool.

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

**6. Durchlauf - grosses reales Projekt-IFC:** 2992 Bauteile geladen,
aber 0 Flaechen/Linien bei ALLEN 5 Beispiel-Schnitten. Zwei getrennte
Ursachen:

1. **Echter Bug:** Viele `IfcWall`-Instanzen (alle vom selben Typ
   "..._Aussenwand_Fassade_36,5_Typ_1") scheiterten mit
   `Failed to process shape`, Representation `('Axis', 'Curve2D')`.
   `ifcopenshell.geom.create_shape(settings, element)` ohne explizite
   Repraesentation kann bei Elementen mit mehreren Shape-Repraesentationen
   (Axis/FootPrint/Body) die falsche erwischen - hier eine 2D-Kurve statt
   des 3D-Volumens. Fix: `ifc_reader._get_body_representation` sucht
   gezielt die 'Body' (Fallback 'Body-Fallback') Subcontext-Repraesentation
   ueber `ifcopenshell.util.representation.get_representation(element,
   "Model", "Body")` und uebergibt sie explizit an `create_shape`.
   Regressionsgetestet gegen die Demo-IFC (unveraendert 26 Flaechen bei
   x=34750).
2. **Keine Geometrie-Luecke, sondern falsche Koordinaten:** die 5
   Beispiel-Schnitte waren mit der Bounding-Box der *Demo-IFC* berechnet
   - bei einem anderen, echten Gebaeude liegen diese Ebenen schlicht
   ausserhalb des Gebaeudes. Neues Hilfsskript
   [`generator_tool/ifc_bbox.py`](../generator_tool/ifc_bbox.py) gibt
   fuer eine beliebige IFC-Datei Bounding-Box + Geschosshoehen aus, damit
   sich sinnvolle Ursprung/Richtung-Werte selbststaendig ermitteln
   lassen (kein Cadwork noetig, laeuft mit der generator_tool-venv).

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
- [x] **Etappe 4**: Cadwork-Plugin - Importer: Zwischendateien einlesen,
      Flaechen (`create_polygon_panel`) + Linien (`create_line_points`)
      erzeugen, alten Import derselben Schnitt-Bezeichnung ersetzen
      (`SchnittImporterService.import_schnitt`). Ablauf-Logik per
      Mock-Cadwork-Modulen durchgetestet (17/68 Flaechen/Linien der
      echten Demo-IFC-Ausgabe korrekt verarbeitet, Ersetzungs-Logik
      verifiziert) - **echter Cadwork-Livetest (Etappe 6) noch offen**,
      insbesondere ob `create_polygon_panel` absolute 3D-Vertices wie
      angenommen entgegennimmt.
- [x] **Etappe 5 (Teil 1)**: "IFC Schnitt Generator"-Fenster kann das
      externe `generator_tool` jetzt direkt anstossen - IFC-Datei per
      Dateidialog waehlen (Pfad wird gemerkt), Knopf "Schnitte
      generieren" fuehrt Export + Subprozess-Aufruf der
      `generator_tool`-venv in einem Schritt aus und zeigt Ergebnis/
      Fehler an. `SchnittGeneratorService.generate_schnitte(ifc_datei)`.
      Voraussetzung: `generator_tool/.venv` einmalig eingerichtet (siehe
      `generator_tool/README.md`); ohne venv erscheint eine klare
      Anleitung statt eines kryptischen Fehlers.
      End-to-end mit gefaelschten Cadwork-Modulen + echtem
      Subprozess-Aufruf verifiziert (Attribut -> Export ->
      generator_tool-venv -> .ifccut.json, 26 Flaechen/108 Linien).
- [ ] **Etappe 5 (Teil 2)**: weiterer UI/UX-Feinschliff (Fortschrittsanzeige
      waehrend der Generierung, Vorschau vor dem Import)
- [ ] **Etappe 6**: Cadwork-Livetest der gesamten Kette, danach Test mit
      echten Projektdaten, Rollout

## Etappe 6 - Livetest-Erkenntnisse (laufend)

**2026-08-10, 1. Durchlauf:** `create_polygon_panel` schlug fuer alle
Flaechen fehl: `incompatible function arguments`. Ursache: die Cadwork-
API-Funktionen erwarten ihre eigenen pybind11-Typen
(`cadwork.point_3d`, `cadwork.vertex_list`), keine reinen Python-Tupel/
Listen - anders als z.B. `bim_controller`/`attribute_controller`, die
mit einfachen Python-Werten arbeiten. Behoben: neue
`cadwork_api/cadwork_core.py` (Wrapper um das Basismodul `cadwork`,
analog zu `shb_toolcenter.cadwork_api.cadwork_core`) plus
`_point_3d`/`_vertex_list`-Konvertierung in
`schnitt_importer/service.py`, bevor `create_polygon_panel`/
`create_line_points` aufgerufen werden. Mit einem gefaelschten
`cadwork`-Modul (das denselben Typfehler erzwingen wuerde, faellt bei
falscher Konvertierung durch) erneut durchgetestet.

**2026-08-10, 2. Durchlauf:** viele Flaechen kamen als Dreiecke statt
mit allen Wand-Eckpunkten zurueck. Mit der Demo-IFC an ueber 100
Ebenen (horizontal 0-3000mm, vertikal 15000-55000mm in 500mm-Schritten)
nicht reproduzierbar (durchgehend korrekte Vierecke/Sechsecke/Achtecke)
- vermutlich ein Sonderfall im echten Projekt (Oeffnung, Ecke, oder ein
Punkt, an dem mehrere Schnittsegmente numerisch sehr nah zusammen-
fallen). Wahrscheinlichste Ursache trotzdem behoben:
`_chain_segments` in `schnitt_berechnung.py` wählte an Verzweigungs-
punkten (>2 anliegende Segmente auf demselben gerundeten Punkt) bisher
einfach die erste gefundene Fortsetzung - das kann eine Kette an der
falschen Stelle schliessen und ein Fragment/Dreieck statt der vollen
Kontur liefern. Jetzt wird die Fortsetzung gewaehlt, die am
"geradesten" zur bisherigen Laufrichtung passt (kleinster Winkel,
Standardtechnik beim Rekonstruieren von Konturen aus Schnittsegmenten).
Regressionsgetestet (Wuerfel-Unit-Tests weiterhin gruen, Demo-IFC-Sweep
weiterhin ohne Dreiecke) - **Bestaetigung am echten Projekt steht noch
aus**, dafuer waere die betroffene `.ifccut.json`-Datei (oder die
Schnitt-Definition, die zum Dreieck-Fall gefuehrt hat) hilfreich.

**Mehrere Schnitte pro Element:** urspruenglich erlaubte das
Benutzerattribut nur EINE Schnitt-Definition pro Element. Erste
Erweiterung auf mehrzeiligen Text in einem Attribut
(`SchnittDefinition.parse_multiple_from_text`) scheiterte im Livetest:
**Cadwork-Benutzerattribute sind auf ca. 128 Zeichen begrenzt** - eine
zweite Zeile wurde exakt bei 128 Zeichen abgeschnitten. Endgueltige
Loesung: mehrere Attribut-**Nummern** statt mehrerer Zeilen
(`SchnittDefinitionConfig.attribute_numbers()`, Standard 20-29 = bis zu
10 Schnitte je Element). `parse_multiple_from_text` bleibt als
Bonus-Unterstuetzung fuer kurze mehrzeilige Faelle erhalten, ist aber
nicht mehr der empfohlene Weg (siehe UI-Hinweistext im Generator-
Fenster).

**Flaechen wurden falsch/unvollstaendig gezeichnet:** `create_polygon_panel`
schliesst den uebergebenen Umriss nicht selbst - der letzte Punkt der
`vertex_list` muss explizit eine Wiederholung des ersten sein, sonst
fehlt die letzte Kante der Flaeche. `ergebnis.flaechen` speichert
weiterhin das einfache (nicht geschlossene) Polygon (siehe
`schnitt_format.py`); `schnitt_importer/service.py` haengt den
Schlusspunkt jetzt unmittelbar vor dem `create_polygon_panel`-Aufruf an.

**BG/BUG + verbundene Konturen (2026-08-10):** drei Aenderungen auf
Wunsch nach dem 3. Livetest:

- Importierte Elemente bekommen jetzt BG (Baugruppe) = Schnittname und
  BUG (Bauuntergruppe) = `ReferenceGeometryConfig.BAUUNTERGRUPPE`
  ("Grundrisse/Schnitte" - dieselbe Konvention wie
  `shb_toolcenter.features.cut_handling`) statt eines eigenen
  "IFC-Referenz"-Gruppennamens.
- Die Kontur einer Flaeche wird jetzt als EIN zusammenhaengendes
  `create_spline_line`-Element ueber den ganzen geschlossenen
  Eckpunktring erzeugt, statt vieler einzelner
  `create_line_points`-Segmente je Kante. `schnitt_berechnung.py`
  erzeugt dafuer bei geschlossenen Ketten keine `SchnittLinie`-Eintraege
  mehr (nur noch die `SchnittFlaeche`) - `linien` im Zwischenformat
  enthaelt jetzt nur noch echte offene Restfragmente (in der Praxis
  bisher nie beobachtet).
- 5 Beispiel-Schnitt-Definitionen fuer die Demo-IFC berechnet und
  verifiziert (siehe Antwort im Chat) - fertig zum Einfuegen in die
  Benutzerattribute 20-24 eines Testelements.

**4. Durchlauf:** Flaechen funktionieren jetzt einwandfrei, aber die
Konturlinien (`create_spline_line`) nicht mehr. Erster Versuch: Ursache
sei der doppelte Schlusspunkt (anders als bei `create_polygon_panel`)
- behoben, aber im 5. Durchlauf weiterhin fehlerhaft.

**5. Durchlauf - `create_spline_line` komplett verworfen:** laut
Anwender kann ein Cadwork-Linienelement grundsaetzlich nur 2 Punkte
tragen - ein Umriss mit mehr als 2 Punkten muss also als MEHRERE
2-Punkt-Linien abgebildet werden, nicht als ein Mehrpunkt-/Spline-
Element. `create_spline_line` war damit von Anfang an der falsche
Ansatz fuer diesen Anwendungsfall (unabhaengig vom Schliessungs-Detail).
Zurueckgebaut auf `create_line_points` je Kante des geschlossenen
Eckpunktrings (inkl. Schlusskante zurueck zum ersten Punkt) - identisch
zum urspruenglichen, nachweislich funktionierenden Ansatz vor der
"eine Kontur = ein Element"-Idee. "Verbunden" heisst hier: alle Kanten
inkl. Schlusskante werden erzeugt und teilen sich Endpunkte, nicht ein
einzelnes Cadwork-Element.
Das erklaert vermutlich einen Teil der zuvor beobachteten
"Dreiecke"/fehlerhaften Flaechen mit.
