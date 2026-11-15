"""Unit-Tests fuer die Cadwork-seitigen Services mit einer gefaelschten
Cadwork-API (element_controller, attribute_controller, ...).

Prueft vor allem Verhalten, das live nur schwer zu testen ist:
- Import-Reihenfolge (alter Import wird erst NACH dem neuen geloescht)
- Wiederfinden alter Importe (aktueller UND frueherer Marker-Slot)
- generate_schnitte ruft im Hintergrund-Thread KEINE Cadwork-API auf
- nur in diesem Lauf geschriebene Zwischendateien zaehlen als erzeugt

Ausfuehren:
    python ifc_schnitt_importer/tests/unit/test_services.py
(oder mit pytest)
"""

import os
import sys
import tempfile
import textwrap
import threading
import time
import types

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Gefaelschte Cadwork-API
# ---------------------------------------------------------------------------


class FakeModell:
    def __init__(self):
        self.next_id = 1
        self.elements = {}  # id -> {"attrs": {nr: text}, "comment": str, ...}
        self.calls = []  # (name, args) in Aufrufreihenfolge
        self.main_thread = threading.main_thread()
        self.api_calls_off_main_thread = []
        self.fail = set()  # Namen von Funktionen, die eine Exception werfen sollen

    def add(self, attrs=None, comment=""):
        eid = self.next_id
        self.next_id += 1
        self.elements[eid] = {"attrs": dict(attrs or {}), "comment": comment}
        return eid

    def record(self, name, *args):
        if threading.current_thread() is not self.main_thread:
            self.api_calls_off_main_thread.append(name)
        self.calls.append((name, args))
        if name in self.fail:
            raise RuntimeError(f"{name} (simulierter Fehler)")


MODELL = FakeModell()


def _install_fake_cadwork():
    m = MODELL

    ec = types.ModuleType("element_controller")
    ec.get_all_identifiable_element_ids = lambda: (m.record("get_all_identifiable_element_ids"), list(m.elements))[1]

    def create_surface(vertices):
        m.record("create_surface", len(vertices))
        return m.add()

    def create_line_points(a, b):
        m.record("create_line_points")
        return m.add()

    def delete_elements_with_undo(ids):
        m.record("delete_elements_with_undo", list(ids))
        for i in ids:
            m.elements.pop(i, None)

    def filter_elements(ids, element_filter):
        m.record("filter_elements")
        nr, wert = element_filter.user_attribute
        return [i for i in ids if m.elements[i]["attrs"].get(nr) == wert]

    ec.create_surface = create_surface
    ec.create_line_points = create_line_points
    ec.delete_elements_with_undo = delete_elements_with_undo
    ec.join_elements = lambda ids: m.record("join_elements", list(ids))
    ec.filter_elements = filter_elements

    ac = types.ModuleType("attribute_controller")
    ac.get_user_attribute = lambda eid, nr: (m.record("get_user_attribute"), m.elements[eid]["attrs"].get(nr, ""))[1]
    ac.get_comment = lambda eid: (m.record("get_comment"), m.elements[eid]["comment"])[1]
    ac.set_user_attribute_name = lambda nr, name: m.record("set_user_attribute_name", nr, name)

    def set_user_attribute(ids, nr, text):
        m.record("set_user_attribute", nr)
        for i in ids:
            m.elements[i]["attrs"][nr] = text

    def set_comment(ids, text):
        m.record("set_comment")
        for i in ids:
            m.elements[i]["comment"] = text

    ac.set_user_attribute = set_user_attribute
    ac.set_comment = set_comment
    ac.set_group = lambda ids, v: m.record("set_group")
    ac.set_subgroup = lambda ids, v: m.record("set_subgroup")
    ac.set_name = lambda ids, v: m.record("set_name")

    vc = types.ModuleType("visualization_controller")
    vc.set_color = lambda ids, c: m.record("set_color")

    uc = types.ModuleType("utility_controller")
    uc.get_project_number = lambda: (m.record("get_project_number"), "P42")[1]
    uc.get_3d_file_path = lambda: (m.record("get_3d_file_path"), m.path_3d)[1]

    cw = types.ModuleType("cadwork")

    class point_3d(tuple):
        def __new__(cls, x, y, z):
            return tuple.__new__(cls, (x, y, z))

    class vertex_list(list):
        pass

    class element_filter:
        def set_user_attribute(self, nr, wert):
            self.user_attribute = (nr, wert)

    cw.point_3d = point_3d
    cw.vertex_list = vertex_list
    cw.element_filter = element_filter

    for name, mod in {
        "element_controller": ec,
        "attribute_controller": ac,
        "visualization_controller": vc,
        "utility_controller": uc,
        "cadwork": cw,
        "geometry_controller": types.ModuleType("geometry_controller"),
        "bim_controller": types.ModuleType("bim_controller"),
    }.items():
        sys.modules[name] = mod


_install_fake_cadwork()

from ifc_schnitt_importer.app.config import ReferenceGeometryConfig, SchnittDefinitionConfig  # noqa: E402
from ifc_schnitt_importer.features.schnitt_generator.service import ProjektKontext, SchnittGeneratorService  # noqa: E402
from ifc_schnitt_importer.features.schnitt_importer.service import SchnittImporterService  # noqa: E402
from ifc_schnitt_importer.shared.schnitt_format import (  # noqa: E402
    FORMAT_VERSION,
    SchnittEbene,
    SchnittErgebnis,
    SchnittFlaeche,
)

MARKER = ReferenceGeometryConfig.IMPORT_MARKER_ATTRIBUTE_NUMBER
LEGACY = ReferenceGeometryConfig.LEGACY_IMPORT_MARKER_ATTRIBUTE_NUMBERS[0]
TAG = ReferenceGeometryConfig.COMMENT_TAG


def _reset():
    global MODELL
    MODELL.__init__()


def _ergebnis(name="Schnitt A", n_flaechen=2):
    quadrat = [[0, 0, 0], [1000, 0, 0], [1000, 1000, 0], [0, 1000, 0]]
    return SchnittErgebnis(
        format_version=FORMAT_VERSION,
        schnitt_name=name,
        schnitt_typ="horizontal",
        projekt_nummer="P42",
        quelle_ifc_datei="x.ifc",
        erzeugt_am="",
        ebene=SchnittEbene(origin=[0, 0, 0], normal=[0, 0, 1]),
        flaechen=[SchnittFlaeche(vertices=quadrat) for _ in range(n_flaechen)],
    )


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


def test_import_loescht_alten_import_erst_nach_dem_erzeugen():
    _reset()
    alt = MODELL.add({MARKER: "Schnitt A"}, TAG)
    fremd = MODELL.add({MARKER: "Schnitt B"}, TAG)

    result = SchnittImporterService().import_schnitt(_ergebnis())

    namen = [c[0] for c in MODELL.calls]
    assert namen.index("delete_elements_with_undo") > max(i for i, n in enumerate(namen) if n == "create_surface")
    assert alt not in MODELL.elements, "alter Import muss ersetzt sein"
    assert fremd in MODELL.elements, "Import eines anderen Schnitts darf nicht geloescht werden"
    assert result.ersetzte_alte_elemente == 1
    assert result.erzeugte_flaechen == 2
    assert result.flaechen_verbunden
    neue = [i for i, e in MODELL.elements.items() if e["attrs"].get(MARKER) == "Schnitt A"]
    assert len(neue) == 2 and all(MODELL.elements[i]["comment"] == TAG for i in neue)


def test_import_findet_alten_marker_slot_nur_mit_import_kommentar():
    _reset()
    legacy_import = MODELL.add({LEGACY: "Schnitt A"}, TAG)
    # Gleicher Text im alten Slot, aber KEIN Import-Element (z.B. Benutzer-
    # attribut eines echten Bauteils) - darf nicht geloescht werden.
    fremdes_bauteil = MODELL.add({LEGACY: "Schnitt A"}, "Wand")

    SchnittImporterService().import_schnitt(_ergebnis())

    assert legacy_import not in MODELL.elements
    assert fremdes_bauteil in MODELL.elements


def test_alter_import_bleibt_wenn_nichts_erzeugt_werden_konnte():
    _reset()
    alt = MODELL.add({MARKER: "Schnitt A"}, TAG)
    MODELL.fail.add("create_surface")

    result = SchnittImporterService().import_schnitt(_ergebnis())

    assert alt in MODELL.elements
    assert result.ersetzte_alte_elemente == 0
    assert result.fehler


def test_marker_wird_trotz_fehler_bei_set_group_gesetzt():
    _reset()
    MODELL.fail.add("set_group")

    result = SchnittImporterService().import_schnitt(_ergebnis())

    neue = [i for i, e in MODELL.elements.items() if e["attrs"].get(MARKER) == "Schnitt A"]
    assert len(neue) == 2, "Marker muss unabhaengig von set_group gesetzt werden"
    assert any("BG" in f.beschreibung for f in result.fehler)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _definition(nr_text):
    return {SchnittDefinitionConfig.ATTRIBUTE_NUMBER + i: t for i, t in enumerate(nr_text)}


def test_scan_ignoriert_text_ohne_gleichheitszeichen_und_meldet_duplikate():
    _reset()
    MODELL.add(_definition(["Name=EG/OG;Typ=horizontal;Ursprung=0,0,1000;Richtung=0,0,1", "irgendein Text"]))
    MODELL.add(_definition(["Name=EG_OG;Typ=horizontal;Ursprung=0,0,2000;Richtung=0,0,1"]))
    MODELL.add(_definition(["Name=Kaputt;Typ=vertikal"]))

    export = SchnittGeneratorService().scan_schnitt_definitionen()

    assert [d.name for d in export.definitionen] == ["EG/OG"]
    meldungen = " | ".join(f.fehler for f in export.fehler)
    assert "bereits vergeben" in meldungen
    assert "Fehlende Felder" in meldungen
    assert "irgendein" not in meldungen


_FAKE_CLI = textwrap.dedent(
    """
    import argparse, json, os, sys, time
    sys.path.insert(0, {root!r})
    from ifc_schnitt_importer.shared.schnitt_format import exchange_dateiname
    p = argparse.ArgumentParser()
    p.add_argument("--ifc"); p.add_argument("--definitionen"); p.add_argument("--output")
    a = p.parse_args()
    d = json.load(open(a.definitionen, encoding="utf-8"))
    print("[ifc_reader] 10 Kandidaten-Elemente in 1 Klassen zu pruefen ...")
    for x in d["definitionen"]:
        if x["name"] == "nicht schreiben":
            continue
        ziel = os.path.join(a.output, exchange_dateiname(d["projekt_nummer"], x["name"]))
        open(ziel, "w").write("{{}}")
        print(f"  -> {{x['name']}}: 1 Flaechen, 0 Linien -> {{ziel}}")
    """
)


def test_generate_schnitte_ohne_cadwork_api_im_thread_und_nur_neue_dateien():
    _reset()
    with tempfile.TemporaryDirectory() as tmp:
        MODELL.path_3d = os.path.join(tmp, "modell.3d")
        ifc = os.path.join(tmp, "x.ifc")
        open(ifc, "w").close()
        cli = os.path.join(tmp, "fake_cli.py")
        open(cli, "w", encoding="utf-8").write(_FAKE_CLI.format(root=_PROJECT_ROOT))

        MODELL.add(_definition([
            "Name=Neu;Typ=horizontal;Ursprung=0,0,1000;Richtung=0,0,1",
            "Name=nicht schreiben;Typ=horizontal;Ursprung=0,0,2000;Richtung=0,0,1",
        ]))

        service = SchnittGeneratorService()
        service._venv_python_path = lambda: sys.executable
        service._cli_script_path = lambda: cli

        kontext = service.projekt_kontext()
        export, definitionen_datei = service.export_schnitt_definitionen(kontext)

        # Alte Datei vom "letzten Lauf" fuer den Schnitt, der diesmal nicht
        # geschrieben wird - darf NICHT als erzeugt zaehlen.
        alt = os.path.join(os.path.dirname(definitionen_datei), "P42_nicht schreiben.ifccut.json")
        open(alt, "w").close()
        alte_zeit = time.time() - 3600
        os.utime(alt, (alte_zeit, alte_zeit))

        zeilen = []
        holder = {}

        def worker():
            holder["r"] = service.generate_schnitte(ifc, export, definitionen_datei, kontext, line_callback=zeilen.append)

        t = threading.Thread(target=worker)
        t.start()
        t.join(60)

        result = holder["r"]
        assert result.subprocess_erfolgreich
        assert [os.path.basename(p) for p in result.erzeugte_dateien] == ["P42_Neu.ifccut.json"]
        assert MODELL.api_calls_off_main_thread == [], f"Cadwork-API im Thread: {MODELL.api_calls_off_main_thread}"
        assert any("Kandidaten-Elemente" in z for z in zeilen)


def main():
    tests = [(name, fn) for name, fn in globals().items() if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"OK: {name}")
    print(f"\nAlle {len(tests)} Tests erfolgreich.")


if __name__ == "__main__":
    main()
