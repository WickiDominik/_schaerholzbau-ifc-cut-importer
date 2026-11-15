"""Unit-Tests fuer die reinen Python-Formate in shared/ (ohne Cadwork).

Ausfuehren:
    python ifc_schnitt_importer/tests/unit/test_shared_formate.py
(oder mit pytest)
"""

import json
import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ifc_schnitt_importer.app.config import PathConfig, ReferenceGeometryConfig, SchnittDefinitionConfig
from ifc_schnitt_importer.shared.schnitt_definition import SchnittDefinition, SchnittDefinitionError
from ifc_schnitt_importer.shared.schnitt_format import (
    FORMAT_VERSION,
    SchnittEbene,
    SchnittErgebnis,
    SchnittFlaeche,
    SchnittFormatError,
    SchnittLinie,
    exchange_dateiname,
    sicherer_dateiname,
)


def _erwarte_fehler(fn, exc_type, text_fragment=""):
    try:
        fn()
    except exc_type as e:
        assert text_fragment in str(e), f"Fehlermeldung {str(e)!r} enthaelt nicht {text_fragment!r}"
        return
    raise AssertionError(f"{exc_type.__name__} erwartet")


# ---- schnitt_definition ----


def test_parse_gueltige_definition():
    d = SchnittDefinition.parse_from_text("Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789,0;Richtung=0,1,0", 7)
    assert d.name == "Schnitt A-A"
    assert d.typ == "vertikal"
    assert d.ursprung == (1234.5, 6789.0, 0.0)
    assert d.richtung == (0.0, 1.0, 0.0)
    assert d.source_element_id == 7


def test_parse_roundtrip_ueber_to_text():
    original = SchnittDefinition("Grundriss EG", "horizontal", (0.0, 0.0, 1000.0), (0.0, 0.0, 1.0))
    wieder = SchnittDefinition.parse_from_text(original.to_text())
    assert wieder == original


def test_parse_fehlende_felder():
    _erwarte_fehler(lambda: SchnittDefinition.parse_from_text("Name=X;Typ=vertikal"), SchnittDefinitionError, "Ursprung")


def test_parse_ungueltiger_typ():
    _erwarte_fehler(
        lambda: SchnittDefinition.parse_from_text("Name=X;Typ=schraeg;Ursprung=0,0,0;Richtung=1,0,0"),
        SchnittDefinitionError,
        "Typ",
    )


def test_parse_nullvektor():
    _erwarte_fehler(
        lambda: SchnittDefinition.parse_from_text("Name=X;Typ=vertikal;Ursprung=0,0,0;Richtung=0,0,0"),
        SchnittDefinitionError,
        "Nullvektor",
    )


def test_typ_horizontal_mit_horizontaler_normale_ist_fehler():
    _erwarte_fehler(
        lambda: SchnittDefinition.parse_from_text("Name=X;Typ=horizontal;Ursprung=0,0,0;Richtung=1,0,0"),
        SchnittDefinitionError,
        "horizontal",
    )


def test_typ_vertikal_mit_z_normale_ist_fehler():
    _erwarte_fehler(
        lambda: SchnittDefinition.parse_from_text("Name=X;Typ=vertikal;Ursprung=0,0,0;Richtung=0,0,1"),
        SchnittDefinitionError,
        "vertikal",
    )


def test_typ_toleranz_erlaubt_minimale_abweichung():
    # Normale nicht normiert und minimal geneigt (< 1 Grad) - noch gueltig.
    SchnittDefinition.parse_from_text("Name=X;Typ=vertikal;Ursprung=0,0,0;Richtung=100,0,1")
    SchnittDefinition.parse_from_text("Name=X;Typ=horizontal;Ursprung=0,0,0;Richtung=0.01,0,1")
    # Schraeg in der XY-Ebene ist fuer "vertikal" voellig in Ordnung.
    SchnittDefinition.parse_from_text("Name=X;Typ=vertikal;Ursprung=0,0,0;Richtung=1,1,0")


def test_parse_multiple_meldet_fehlerhafte_zeile_und_liest_rest():
    text = "Name=A;Typ=vertikal;Ursprung=0,0,0;Richtung=1,0,0\nkaputt\n\nName=B;Typ=horizontal;Ursprung=0,0,0;Richtung=0,0,1"
    definitionen, fehler = SchnittDefinition.parse_multiple_from_text(text)
    assert [d.name for d in definitionen] == ["A", "B"]
    assert len(fehler) == 1 and fehler[0].startswith("Zeile 2")


# ---- schnitt_format ----


def test_sicherer_dateiname():
    assert sicherer_dateiname("Schnitt A-A") == "Schnitt A-A"
    assert sicherer_dateiname("EG/OG") == "EG_OG"
    assert sicherer_dateiname("A:A") == "A_A"
    assert sicherer_dateiname('a<b>c"d\\e|f?g*h') == "a_b_c_d_e_f_g_h"
    assert sicherer_dateiname("Schnitt. ") == "Schnitt"
    assert sicherer_dateiname("con") == "_con"
    assert sicherer_dateiname("") == "_"


def test_exchange_dateiname_plugin_und_generator_identisch():
    pfad = PathConfig.get_exchange_file_path(os.path.join("C:", "Projekt", "modell.3d"), "P123", "EG/OG")
    assert os.path.basename(pfad) == exchange_dateiname("P123", "EG/OG") == "P123_EG_OG.ifccut.json"
    assert os.path.dirname(pfad).endswith(PathConfig.EXCHANGE_SUBDIRECTORY)


def _beispiel_ergebnis():
    return SchnittErgebnis(
        format_version=FORMAT_VERSION,
        schnitt_name="Schnitt Ä-Ä",
        schnitt_typ="vertikal",
        projekt_nummer="P1",
        quelle_ifc_datei="x.ifc",
        erzeugt_am="2026-11-15T12:00:00",
        ebene=SchnittEbene(origin=[0, 0, 0], normal=[1, 0, 0], source_element_id=5),
        flaechen=[SchnittFlaeche(vertices=[[0, 0, 0], [0, 1, 0], [0, 1, 1]], ifc_element_type="IfcWall", ifc_guid="G")],
        linien=[SchnittLinie(start=[0, 0, 0], end=[0, 2, 0])],
    )


def test_json_roundtrip():
    original = _beispiel_ergebnis()
    assert SchnittErgebnis.from_json(original.to_json()) == original


def test_unbekannte_felder_werden_ignoriert():
    data = json.loads(_beispiel_ergebnis().to_json())
    data["neues_feld"] = 1
    data["ebene"]["neu"] = 2
    data["flaechen"][0]["farbe"] = 3
    geladen = SchnittErgebnis.from_json(json.dumps(data))
    assert geladen == _beispiel_ergebnis()


def test_neuere_formatversion_wird_abgelehnt():
    data = json.loads(_beispiel_ergebnis().to_json())
    data["format_version"] = FORMAT_VERSION + 1
    _erwarte_fehler(lambda: SchnittErgebnis.from_json(json.dumps(data)), SchnittFormatError, "Formatversion")


# ---- config ----


def test_import_marker_liegt_ausserhalb_der_definitions_attribute():
    definitions_slots = set(SchnittDefinitionConfig.attribute_numbers())
    assert ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER not in definitions_slots


def main():
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"OK: {name}")
    print(f"\nAlle {len(tests)} Tests erfolgreich.")


if __name__ == "__main__":
    main()
