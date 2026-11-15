"""Unit-Tests fuer die Schnitt-Uebersicht des Fensters (reines Python, ohne Cadwork/Tk).

Ausfuehren:
    python ifc_schnitt_importer/tests/unit/test_uebersicht.py
(oder mit pytest)
"""

import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ifc_schnitt_importer.features.schnitt_workflow import uebersicht as ub  # noqa: E402
from ifc_schnitt_importer.shared.schnitt_definition import SchnittDefinition, SchnittDefinitionFehler  # noqa: E402

ABLAGE = os.path.join("C:", "projekt", "IFC_Schnitte")


def _definition(name, typ="horizontal", ursprung=(0, 0, 1000), richtung=(0, 0, 1), element_id=7):
    return SchnittDefinition(name=name, typ=typ, ursprung=ursprung, richtung=richtung, source_element_id=element_id)


def _datei(name, projekt="P42"):
    return os.path.join(ABLAGE, f"{projekt}_{name}.ifccut.json")


def _uebersicht(definitionen=(), fehler=(), dateien=None, importierte=(), ifc=None, zeiten=None):
    zeiten = zeiten or {}
    return ub.baue_uebersicht(
        definitionen, fehler, dateien or [], importierte, "P42",
        ifc_geaendert_am=ifc, mtime=lambda p: zeiten.get(p, 100.0),
    )


def test_status_je_schnitt():
    u = _uebersicht(
        definitionen=[_definition("Neu"), _definition("Bereit"), _definition("Fertig"), _definition("Alt")],
        fehler=[SchnittDefinitionFehler(element_id=9, fehler="Zeile 1: Fehlende Felder: Typ")],
        dateien=[_datei("Bereit"), _datei("Fertig"), _datei("Alt"), _datei("Geloescht")],
        importierte=["Fertig", "Geloescht"],
        ifc=150.0,
        zeiten={_datei("Alt"): 50.0, _datei("Bereit"): 200.0, _datei("Fertig"): 200.0, _datei("Geloescht"): 200.0},
    )
    status = {z.name: z.status for z in u.zeilen}
    assert status == {
        "Alt": ub.VERALTET,
        "Bereit": ub.BEREIT,
        "Fertig": ub.IM_3D,
        "Neu": ub.NICHT_GENERIERT,
        "Geloescht": ub.NUR_ABLAGE,
        "Element 9": ub.FEHLER,
    }
    # Reihenfolge: Definitionen alphabetisch, dann Dateien ohne Definition, dann Fehler
    assert [z.name for z in u.zeilen] == ["Alt", "Bereit", "Fertig", "Neu", "Geloescht", "Element 9"]
    assert u.zeile("geloescht") is None and u.zeilen[4].im_3d
    assert u.anzahl_definitionen == 4
    assert ub.standard_auswahl(u) == ["bereit"]


def test_dateiname_mit_sonderzeichen_und_gross_klein():
    # "EG/OG" wird im Dateinamen zu "EG_OG"; Windows vergleicht ohne Gross-/Kleinschreibung
    datei = os.path.join(ABLAGE, "p42_eg_og.IFCCUT.JSON")
    u = _uebersicht(definitionen=[_definition("EG/OG")], dateien=[datei], importierte=["eg_og"])
    assert len(u.zeilen) == 1
    assert u.zeilen[0].datei == datei
    assert u.zeilen[0].status == ub.IM_3D


def test_ohne_ifc_kein_veraltet():
    u = _uebersicht(definitionen=[_definition("A")], dateien=[_datei("A")], zeiten={_datei("A"): 1.0})
    assert u.zeilen[0].status == ub.BEREIT


def test_naechster_schritt_und_schrittleiste():
    leer = _uebersicht()
    assert ub.naechster_schritt(leer, ifc_gewaehlt=True) == ub.SCHRITT_DEFINIEREN

    offen = _uebersicht(definitionen=[_definition("A")])
    assert ub.naechster_schritt(offen, ifc_gewaehlt=False) == ub.SCHRITT_IFC_WAEHLEN
    assert ub.naechster_schritt(offen, ifc_gewaehlt=True) == ub.SCHRITT_GENERIEREN

    bereit = _uebersicht(definitionen=[_definition("A")], dateien=[_datei("A")])
    assert ub.naechster_schritt(bereit, ifc_gewaehlt=True) == ub.SCHRITT_IMPORTIEREN
    assert ub.schritt_zustaende(ub.SCHRITT_IMPORTIEREN) == {
        "definieren": ub.ERLEDIGT, "generieren": ub.ERLEDIGT, "importieren": ub.AKTIV}

    fertig = _uebersicht(definitionen=[_definition("A")], dateien=[_datei("A")], importierte=["A"])
    assert ub.naechster_schritt(fertig, ifc_gewaehlt=False) == ub.SCHRITT_FERTIG

    # Nur fehlerhafte Definitionen -> noch nichts Brauchbares definiert
    nur_fehler = _uebersicht(fehler=[SchnittDefinitionFehler(element_id=1, fehler="x")])
    assert ub.naechster_schritt(nur_fehler, ifc_gewaehlt=True) == ub.SCHRITT_DEFINIEREN
    for schritt in (ub.SCHRITT_DEFINIEREN, ub.SCHRITT_IFC_WAEHLEN, ub.SCHRITT_GENERIEREN,
                    ub.SCHRITT_IMPORTIEREN, ub.SCHRITT_FERTIG):
        assert ub.HINWEISE[schritt]


def test_ebene_text():
    assert ub.ebene_text(_definition("G", ursprung=(0, 0, 2750))) == "Höhe Z = 2750 mm"
    assert ub.ebene_text(_definition("S", "vertikal", (1234.5, 0, 0), (1, 0, 0))) == "Ebene X = 1234.5 mm"
    assert ub.ebene_text(_definition("S", "vertikal", (0, 6789, 0), (0, 1, 0))) == "Ebene Y = 6789 mm"
    assert ub.ebene_text(_definition("S", "vertikal", (10, 20, 0), (1, 1, 0))).startswith("durch 10 / 20")
    assert ub.zeit_text(None) == "–"


def main():
    tests = [(name, fn) for name, fn in globals().items() if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"OK: {name}")
    print(f"\nAlle {len(tests)} Tests erfolgreich.")


if __name__ == "__main__":
    main()
