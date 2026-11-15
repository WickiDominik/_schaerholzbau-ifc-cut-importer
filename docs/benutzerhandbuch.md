# IFC-Schnitte – Kurzanleitung

Das Fenster führt in drei Schritten von der IFC des Architekten zu
Referenz-Schnitten im 3D-Modell. Die Schrittleiste oben zeigt, wo man
steht, der Hinweis darunter sagt, was als Nächstes zu tun ist, und der
farbige Knopf unten ist immer der nächste Schritt.

## 1. Schnitte definieren

Jeder Schnitt ist ein Text in einem Benutzerattribut (Nr. 20–29) an
einem beliebigen Element, ein Schnitt pro Attribut-Nummer:

```
Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789.0,0;Richtung=0,1,0
Name=Grundriss EG;Typ=horizontal;Ursprung=0,0,1000;Richtung=0,0,1
```

- Name: Schnittname, im ganzen Modell eindeutig (wird zur Baugruppe)
- Typ: horizontal (Grundriss) oder vertikal (Schnitt)
- Ursprung: ein Punkt auf der Schnittebene, x,y,z in mm
- Richtung: die Ebenennormale (horizontal: 0,0,1)

Danach im Fenster «Aktualisieren». Fehlerhafte Definitionen erscheinen
rot in der Tabelle; ein Doppelklick zeigt den Grund und die Element-ID.

## 2. Aus IFC generieren

IFC-Datei wählen (wird pro 3D-Datei gemerkt) und «Schnitte generieren».
Alle definierten Schnitte werden aus der IFC berechnet und als
Zwischendatei im Ordner IFC_Schnitte neben der 3D-Datei abgelegt
(«Ordner öffnen»). Das kann bei grossen IFC einige Minuten dauern;
Cadwork bleibt währenddessen bedienbar.

Ist «Nach dem Generieren direkt importieren» angehakt, werden die neuen
Schnitte anschliessend gleich ins 3D übernommen.

## 3. Ins 3D importieren

Gewünschte Schnitte in der Tabelle anhaken (Klick auf die Zeile, «Alle»,
«Keine») und «Importieren». Die Schnitte erscheinen als Flächen und
Linien in der Bauuntergruppe «Grundrisse/Schnitte», Baugruppe = Name des
Schnitts. Ein erneuter Import ersetzt den früheren Import desselben
Schnitts (rückgängig machbar).

## Status in der Tabelle

- Definition fehlerhaft: Text im Attribut korrigieren, «Aktualisieren»
- Noch nicht generiert: «Schnitte generieren»
- IFC ist neuer – neu generieren: die gewählte IFC ist neuer als die
  Zwischendatei
- Bereit zum Import: generiert, aber noch nicht im 3D
- Im 3D: fertig
- Nur in Ablage: Zwischendatei ohne Definition im Modell (z.B.
  Definition gelöscht); kann trotzdem importiert werden

## Wenn etwas nicht klappt

Ausführliche Meldungen stehen in der Cadwork-Konsole. Fehlt das
Generator-Tool, zeigt «Schnitte generieren» die einmalige
Einrichtungsanleitung (siehe generator_tool/README.md).
