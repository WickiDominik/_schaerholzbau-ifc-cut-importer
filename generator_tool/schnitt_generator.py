"""IFC Schnitt Generator - eigenstaendiges Kommandozeilen-Tool.

Laeuft ausserhalb von Cadwork (siehe README.md fuer Setup). Liest eine
IFC-Datei und die vom Cadwork-Plugin exportierten Schnitt-Definitionen,
berechnet je Definition den Ebenenschnitt und schreibt das Ergebnis als
Zwischendatei fuer den Cadwork-seitigen "IFC Schnitt Importer".

Wird normalerweise vom Cadwork-Plugin als Subprozess gestartet (siehe
ifc_schnitt_importer/features/schnitt_generator/service.py), kann aber
auch direkt im Terminal laufen. Die Fortschrittszeilen auf stdout werden
vom Plugin per Regex ausgewertet (app/main_window.py) - Format beim
Aendern dort mitziehen.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

# Projekt-Root (enthaelt sowohl generator_tool/ als auch
# ifc_schnitt_importer/) auf sys.path, damit beide Pakete importierbar
# sind, egal von wo dieses Skript gestartet wird.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PROJECT_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from generator_tool.core.ifc_reader import lade_bauteile
from generator_tool.core.schnitt_berechnung import berechne_schnitt
from generator_tool.core.schnitt_definitionen import load_schnitt_definitionen
from ifc_schnitt_importer.shared.schnitt_format import (
    FORMAT_VERSION,
    SchnittEbene,
    SchnittErgebnis,
    exchange_dateiname,
    save_schnitt_ergebnis,
)


def parse_args():
    parser = argparse.ArgumentParser(description="IFC Schnitt Generator")
    parser.add_argument("--ifc", required=True, help="Pfad zur IFC-Datei (Archicad-Export)")
    parser.add_argument("--definitionen", required=True, help="Pfad zu schnitt_definitionen.json")
    parser.add_argument("--output", required=True, help="Zielordner fuer die .ifccut.json Ergebnisdateien")
    return parser.parse_args()


def main():
    args = parse_args()

    definitionen_datei = load_schnitt_definitionen(args.definitionen)
    print(f"{len(definitionen_datei.definitionen)} Schnitt-Definition(en) geladen aus {args.definitionen}")

    bauteile = list(lade_bauteile(args.ifc))
    print(f"{len(bauteile)} Bauteile aus {args.ifc} geladen")

    os.makedirs(args.output, exist_ok=True)

    for definition in definitionen_datei.definitionen:
        ebene = SchnittEbene(
            origin=list(definition.ursprung),
            normal=list(definition.richtung),
            source_element_id=definition.source_element_id,
        )
        flaechen, linien = berechne_schnitt(ebene, bauteile)

        ergebnis = SchnittErgebnis(
            format_version=FORMAT_VERSION,
            schnitt_name=definition.name,
            schnitt_typ=definition.typ,
            projekt_nummer=definitionen_datei.projekt_nummer,
            quelle_ifc_datei=args.ifc,
            erzeugt_am=datetime.datetime.now().isoformat(),
            ebene=ebene,
            flaechen=flaechen,
            linien=linien,
        )

        # Gleiche Namensbildung wie im Plugin (PathConfig.get_exchange_file_path),
        # inkl. Bereinigung von unter Windows ungueltigen Zeichen.
        target_path = os.path.join(args.output, exchange_dateiname(definitionen_datei.projekt_nummer, definition.name))
        save_schnitt_ergebnis(ergebnis, target_path)
        print(f"  -> {definition.name}: {len(flaechen)} Flaechen, {len(linien)} Linien -> {target_path}")


if __name__ == "__main__":
    main()
