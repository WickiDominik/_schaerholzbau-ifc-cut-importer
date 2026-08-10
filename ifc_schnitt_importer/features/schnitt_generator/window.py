"""UI window for the Cadwork-side half of the IFC Schnitt Generator.

STATUS: Etappe 2 (implementiert) - Export der Schnitt-Definitionen.
Die eigentliche IFC-Schnittberechnung passiert im externen
generator_tool/ (Etappe 3, noch offen) - siehe docs/konzept.md.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from ifc_schnitt_importer.app.config import AppConfig, SchnittDefinitionConfig
from ifc_schnitt_importer.shared.logging import log_error_json
from ifc_schnitt_importer.shared.window_utils import get_or_create_root


def show_schnitt_generator_window(parent=None):
    root = get_or_create_root(parent)
    root.title(f"{AppConfig.APP_NAME} - Schnitt Generator")
    root.geometry("640x480")

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="IFC Schnitt Generator - Schritt 1: Schnitt-Definitionen exportieren",
        font=("TkDefaultFont", 11, "bold"),
        wraplength=600,
    ).pack(anchor="w")

    ttk.Label(
        frame,
        text=(
            f"Liest bei allen Elementen das Benutzerattribut Nr. {SchnittDefinitionConfig.ATTRIBUTE_NUMBER} "
            f"(\"{SchnittDefinitionConfig.ATTRIBUTE_LABEL}\") und schreibt eine Bruecken-Datei fuer das "
            "externe Generator-Tool.\n\n"
            "Format je Element (ein Benutzerattribut-Text):\n"
            "  Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789.0,0;Richtung=0,1,0\n\n"
            "Schritt 2 (IFC laden + Schnitte berechnen) laeuft ausserhalb von Cadwork im "
            "generator_tool/ - siehe docs/konzept.md (Etappe 3, noch offen)."
        ),
        justify="left",
        wraplength=600,
    ).pack(anchor="w", pady=(10, 10))

    result_text = tk.Text(frame, height=14, wrap="word")
    result_text.pack(fill="both", expand=True, pady=(0, 10))
    result_text.insert("1.0", "Noch nicht ausgefuehrt.")
    result_text.config(state="disabled")

    status_var = tk.StringVar(value="")
    status_label = ttk.Label(frame, textvariable=status_var)
    status_label.pack(anchor="w")

    def _set_result_text(text: str):
        result_text.config(state="normal")
        result_text.delete("1.0", "end")
        result_text.insert("1.0", text)
        result_text.config(state="disabled")

    def _run_export():
        try:
            from ifc_schnitt_importer.features.schnitt_generator.service import SchnittGeneratorService

            service = SchnittGeneratorService()
            service.ensure_attribute_label()
            result, written_path = service.export_schnitt_definitionen()

            lines = [f"{len(result.definitionen)} Schnitt-Definition(en) gefunden:\n"]
            for d in result.definitionen:
                lines.append(f"  - {d.name} ({d.typ}), Element {d.source_element_id}")

            if result.fehler:
                lines.append(f"\n{len(result.fehler)} Element(e) mit ungueltigem Attribut-Text:")
                for f in result.fehler:
                    lines.append(f"  - Element {f.element_id}: {f.fehler}")

            lines.append(f"\nGeschrieben nach:\n  {written_path}")
            _set_result_text("\n".join(lines))
            status_var.set(f"Fertig: {len(result.definitionen)} Definition(en), {len(result.fehler)} Fehler")
        except Exception as e:
            _set_result_text(f"Fehler beim Export: {e}")
            status_var.set("Fehler - siehe Log")
            log_error_json(e, module=__name__, action="export_schnitt_definitionen", function_name="_run_export")
            import traceback

            traceback.print_exc()

    button_row = ttk.Frame(frame)
    button_row.pack(fill="x")
    ttk.Button(button_row, text="Schnitt-Definitionen exportieren", command=_run_export).pack(side="left")
    ttk.Button(button_row, text="Schliessen", command=root.destroy).pack(side="right")

    if isinstance(root, tk.Tk):
        root.mainloop()
