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
| Woher kommt die Schnittlage? | Abgeleitet aus bestehenden **Cadwork-Ausgabeelementen** (Planausgabe-Objekte, die die Holzbauplanung bereits fuer ihre eigene 2D-Planausgabe - Grundrisse UND Schnitte - im 3D-Modell platziert) |
| Zweck der importierten Fl./Lin. | Konstruktionsgrundlage fuer die Ausfuehrungsplanung - praezise, reproduzierbar, klar von echten Bauteilen getrennt |
| Koordinatensystem | Vorerst 1:1 Uebernahme (IFC- und Cadwork-Modell teilen sich denselben Nullpunkt); spaetere Kalibrierung als Erweiterung offen |
| Projektstruktur | Eigenstaendiges Cadwork-Plugin (eigener Ordner `_schaerholzbau-ifc-schnitt-importer`, eigene `plugin_info.xml`), ein Plugin mit zwei Menuepunkten (Generator + Importer) |

## Warum kein ifcopenshell

Cadwork SP2026 laeuft auf Python 3.14 (siehe Toolcenter
`docs/architecture.md`). `ifcopenshell` bietet aktuell keine Wheels fuer
Python 3.13/3.14 (gepruefte PyPI-Metadaten, Stand 2026-08-10) - eine reine
Python-IFC-Parsing-Loesung waere fuer SP2026 gar nicht installierbar.

**Stattdessen:** Cadworks eigener `bim_controller` bietet
`import_ifc_return_exchange_objects(file_path)` - nativer, lagerichtiger
IFC-Import als leichte "Exchange Objects" (keine vollwertigen Bauteile,
kein Stuecklisten-Einfluss), plus `convert_exchange_objects(...)` um
gezielt einzelne davon in echte Geometrie umzuwandeln. Das loest gleich
zwei Probleme: keine externe Abhaengigkeit noetig, UND die IFC-Platzierung
(Standort/Rotation) wird von Cadworks eigenem, ausgereiften IFC-Importer
uebernommen statt selbst nachgebaut zu werden.

Quelle: [docs.cadwork.com - bim_controller](https://docs.cadwork.com/projects/cwapi3dpython/en/latest/documentation/bim_controller/)
(abgerufen 2026-08-10).

## Architektur

Zwei-Phasen-Workflow mit Zwischenformat (analog zum bestehenden
`.cut3d`-Muster in `shb_toolcenter/features/cut_handling`):

```
Phase A - Schnitt-Generator                Phase B - Schnitt-Importer
--------------------------------           ---------------------------
1. IFC laden (bim_controller.              1. Zwischendatei(en) waehlen
   import_ifc_return_exchange_objects)     2. Je Schnitt: Flaechen
2. Ausgabeelement(e) waehlen ->               (create_polygon_panel) +
   Ursprung + Normale + Ausdehnung             Linien (create_line_points)
3. Je Schnitt: betroffene Exchange-           an IFC-Originalposition
   Objects konvertieren, mit Ebene            erzeugen, eigene Gruppe
   schneiden (cut_element_with_plane)         "IFC-Referenz - <Name>"
4. Ergebnis in Zwischenformat               3. Vorherigen Import desselben
   schreiben (siehe shared/schnitt_          Schnitts ersetzen
   format.py): <projekt>_<schnitt>
   .ifccut.json
```

Warum die Trennung: einmal generieren (rechenintensiv, ganze IFC),
beliebig oft / von mehreren Personen importieren, ohne die IFC jedes Mal
neu zu parsen.

## Offene technische Punkte (Etappe 0 - Spike)

Aus der Online-API-Doku (docs.cadwork.com) konnten folgende Punkte NICHT
abschliessend verifiziert werden (Doku-Seiten teils zu lang fuer
automatisiertes Abrufen) und muessen direkt in Cadwork getestet werden,
bevor Etappe 2/3 darauf aufbauen:

1. **Ausgabeelement-Ebene auslesen**: Vermutung - generische
   `geometry_controller`-Funktionen (`get_p1`, `get_xl`, `get_yl`,
   `get_zl`) liefern Ursprung + lokale Achsen auch fuer Ausgabeelemente,
   da sie fuer jedes Element mit lokalem Koordinatensystem gelten sollten.
2. **`cut_element_with_plane`**: Existenz in `element_controller`
   mehrfach bestaetigt, genaue Signatur/Verhalten (mutiert das Element
   oder liefert es ein neues Schnitt-Ergebnis?) unklar.
3. **Bounding/Positionierung nach IFC-Import**: bestaetigen, dass
   `import_ifc_return_exchange_objects` tatsaechlich lagerichtig
   (gleiche Koordinaten wie im IFC) importiert.
4. **Geschoss-System**: pruefen, ob `bim_controller.get_all_storeys` nach
   IFC-Import die IFC-Storeys widerspiegelt (fuer horizontale Schnitte
   evtl. eine zusaetzliche/alternative Hoehenquelle zu den
   Ausgabeelementen).

Testskript: [`ifc_schnitt_importer/tests/manual/api_spike.py`](../ifc_schnitt_importer/tests/manual/api_spike.py).
Ergebnis bitte zurueckmelden (Konsolen-Output oder die generierte
`logs/api_spike_results.json`), dann werten wir das gemeinsam aus und
schaerfen Etappe 2/3 entsprechend nach.

## Datenformat (Generator -> Importer)

Siehe [`ifc_schnitt_importer/shared/schnitt_format.py`](../ifc_schnitt_importer/shared/schnitt_format.py)
fuer die konkreten Datenklassen (`SchnittEbene`, `SchnittFlaeche`,
`SchnittLinie`, `SchnittErgebnis`) und JSON (de)serialisierung.

## Etappenplan

- [x] **Etappe 0**: API-Spike (offene Punkte oben verifizieren)
- [x] **Etappe 1**: Projekt-Grundgeruest, Plugin-Registrierung, Menu mit
      zwei Platzhalter-Fenstern (dieser Stand)
- [ ] **Etappe 2**: Generator - Ausgabeelement-Auswahl-UI + Schnittebene-
      Extraktion (`SchnittGeneratorService.list_ausgabeelemente` /
      `get_schnittebene`)
- [ ] **Etappe 3**: Generator - IFC-Import + Schnittberechnung +
      Export der Zwischendatei (`import_ifc` / `berechne_schnitt`)
- [ ] **Etappe 4**: Importer - Zwischendatei einlesen, Flaechen/Linien
      erzeugen, alten Import ersetzen (`SchnittImporterService.import_schnitt`)
- [ ] **Etappe 5**: UI/UX-Feinschliff (Fortschrittsanzeige, Fehlerbilder,
      Vorschau vor Import)
- [ ] **Etappe 6**: Test mit echten Projektdaten, Rollout
