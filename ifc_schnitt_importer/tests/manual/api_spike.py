"""Etappe 0 - API-Spike: verifiziert die Kern-Annahmen der Architektur
direkt gegen die laufende Cadwork-API, BEVOR Etappe 2/3 darauf aufbauen.

Prueft:
  1. bim_controller.import_ifc_return_exchange_objects(...) - lagerichtiger
     IFC-Import als leichte Exchange Objects (Kernmechanismus statt ifcopenshell)
  2. bim_controller.convert_exchange_objects(...) - Umwandlung in echte Geometrie
  3. Geometrie-Abfrage eines vom Benutzer vorher ausgewaehlten Ausgabeelements/
     einer Achse (get_p1/get_p2/get_p3/get_xl/get_yl/get_zl) - moegliche Quelle
     der Schnittebene
  4. element_controller.cut_element_with_plane(...) - Existenz/Signatur
  5. bim_controller.get_all_storeys / get_active_building / get_storey_height

WIE AUSFUEHREN (analog docs/developer_guide.md der schaerholzbau Toolcenter):
  1. Cadwork oeffnen, das Zielprojekt laden.
  2. Im 3D-Modell das gewuenschte Ausgabeelement (oder eine Achse) EINMALIG
     auswaehlen/aktivieren (Testkandidat fuer Schritt 3).
  3. IFC_PATH unten ggf. anpassen (Default: mitgelieferte Demo-IFC).
  4. Terminal: die python.exe aus dem Cadwork-Python-Ordner verwenden, z.B.
       "<CADWORK>\\pythonAddIn\\python.exe" -B ifc_schnitt_importer\\tests\\manual\\api_spike.py
     (gleiches Vorgehen wie bei den vorhandenen shb_toolcenter/tests/manual Skripten)
  5. Ergebnis wird auf der Konsole ausgegeben UND als JSON gespeichert unter
       ifc_schnitt_importer/logs/api_spike_results.json
     -> dieses File bitte zurueckmelden/teilen, dann werten wir es gemeinsam aus.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import traceback

IFC_PATH = r"C:\Users\dominik.wicki\Downloads\Archicad Demoprojekt Bürogebäude.ifc"

RESULTS = {"timestamp": datetime.datetime.now().isoformat(), "checks": []}


def check(name):
    def _decorator(fn):
        def _wrapped():
            entry = {"name": name, "status": "UNKNOWN", "detail": ""}
            try:
                detail = fn()
                entry["status"] = "PASS"
                entry["detail"] = detail if isinstance(detail, str) else json.dumps(detail, default=str)
            except NotImplementedError as e:
                entry["status"] = "SKIPPED"
                entry["detail"] = str(e)
            except Exception as e:
                entry["status"] = "FAIL"
                entry["detail"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            RESULTS["checks"].append(entry)
            print(f"[{entry['status']}] {name}: {entry['detail'][:300]}")
            return entry
        return _wrapped
    return _decorator


@check("import bim_controller")
def check_bim_import():
    import bim_controller as bc  # noqa: F401
    return "bim_controller importierbar"


@check("import element_controller / geometry_controller")
def check_core_imports():
    import element_controller as ec  # noqa: F401
    import geometry_controller as gc  # noqa: F401
    return "element_controller und geometry_controller importierbar"


@check("bim_controller.import_ifc_return_exchange_objects")
def check_ifc_import():
    import bim_controller as bc

    if not os.path.exists(IFC_PATH):
        raise FileNotFoundError(f"Demo-IFC nicht gefunden unter {IFC_PATH}")

    exchange_ids = bc.import_ifc_return_exchange_objects(IFC_PATH)
    if not exchange_ids:
        raise RuntimeError("Import lieferte keine Exchange-Object-IDs")

    return {"count": len(exchange_ids), "sample_ids": list(exchange_ids[:5])}


@check("Position/Bounding-Box der importierten Exchange Objects")
def check_ifc_bounds():
    import bim_controller as bc
    import geometry_controller as gc

    if not os.path.exists(IFC_PATH):
        raise NotImplementedError("uebersprungen: Demo-IFC fehlt")

    exchange_ids = bc.import_ifc_return_exchange_objects(IFC_PATH)
    sample = list(exchange_ids[: min(20, len(exchange_ids))])

    points = []
    for eid in sample:
        for fn_name in ("get_p1", "get_p2", "get_p3"):
            fn = getattr(gc, fn_name, None)
            if fn is None:
                continue
            try:
                points.append(tuple(fn(eid)))
            except Exception:
                pass

    if not points:
        raise RuntimeError("Keine Punktdaten ueber get_p1/p2/p3 verfuegbar (Exchange Objects evtl. ohne direkte Geometrie)")

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return {
        "n_points": len(points),
        "bbox_min": [min(xs), min(ys), min(zs)],
        "bbox_max": [max(xs), max(ys), max(zs)],
    }


@check("bim_controller.convert_exchange_objects (kleine Stichprobe)")
def check_convert_exchange_objects():
    import bim_controller as bc

    if not os.path.exists(IFC_PATH):
        raise NotImplementedError("uebersprungen: Demo-IFC fehlt")

    exchange_ids = bc.import_ifc_return_exchange_objects(IFC_PATH)
    sample = list(exchange_ids[:3])
    converted = bc.convert_exchange_objects(sample)
    return {"input": sample, "converted_ids": list(converted)}


@check("Geometrie eines vorher vom Benutzer ausgewaehlten Elements (Ausgabeelement/Achse)")
def check_selected_element_geometry():
    import element_controller as ec
    import geometry_controller as gc

    selected = None
    for fn_name in ("get_active_identifiable_element_ids", "get_selected_element_ids", "get_active_element_ids"):
        fn = getattr(ec, fn_name, None)
        if fn is None:
            continue
        try:
            ids = fn()
            if ids:
                selected = list(ids)
                break
        except Exception:
            continue

    if not selected:
        raise NotImplementedError(
            "uebersprungen: kein Element vorausgewaehlt - bitte vor dem Lauf ein "
            "Ausgabeelement/eine Achse im Modell aktivieren"
        )

    eid = selected[0]
    result = {"element_id": eid}
    for fn_name in ("get_p1", "get_p2", "get_p3", "get_xl", "get_yl", "get_zl", "get_element_vertices"):
        fn = getattr(gc, fn_name, None)
        if fn is None:
            result[fn_name] = "nicht vorhanden"
            continue
        try:
            result[fn_name] = fn(eid) if fn_name != "get_element_vertices" else f"{len(fn(eid))} vertices"
        except Exception as e:
            result[fn_name] = f"FEHLER: {e}"
    return result


@check("element_controller.cut_element_with_plane vorhanden")
def check_cut_element_with_plane():
    import element_controller as ec

    fn = getattr(ec, "cut_element_with_plane", None)
    if fn is None:
        raise RuntimeError("cut_element_with_plane nicht in element_controller gefunden")

    import inspect

    try:
        sig = str(inspect.signature(fn))
    except (TypeError, ValueError):
        sig = "(Signatur nicht introspizierbar - haeufig bei C-Extension-Funktionen)"
    return f"gefunden, Signatur: {sig}"


@check("bim_controller Geschoss-/Storey-System")
def check_storeys():
    import bim_controller as bc

    building = bc.get_active_building()
    storeys = bc.get_all_storeys(building)
    heights = {}
    for storey in storeys:
        try:
            heights[storey] = bc.get_storey_height(building, storey)
        except Exception as e:
            heights[storey] = f"FEHLER: {e}"
    return {"active_building": building, "storeys": storeys, "heights": heights}


def main():
    print("=" * 80)
    print("IFC Schnitt Importer - API Spike (Etappe 0)")
    print("=" * 80)

    for fn in (
        check_bim_import,
        check_core_imports,
        check_ifc_import,
        check_ifc_bounds,
        check_convert_exchange_objects,
        check_selected_element_geometry,
        check_cut_element_with_plane,
        check_storeys,
    ):
        fn()

    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    results_path = os.path.join(log_dir, "api_spike_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False, default=str)

    print("=" * 80)
    print(f"Ergebnisse gespeichert unter: {results_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
