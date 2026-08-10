"""UI window for the IFC Schnitt Importer.

STATUS: Etappe 4 (implementiert) - siehe docs/konzept.md.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from ifc_schnitt_importer.app.config import AppConfig
from ifc_schnitt_importer.shared.logging import log_error_json
from ifc_schnitt_importer.shared.window_utils import get_or_create_root


def show_schnitt_importer_window(parent=None):
    root = get_or_create_root(parent)
    root.title(f"{AppConfig.APP_NAME} - Schnitt Importer")
    root.geometry("640x480")

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="IFC Schnitt Importer",
        font=("TkDefaultFont", 11, "bold"),
    ).pack(anchor="w")

    ttk.Label(
        frame,
        text="Vom externen Generator-Tool erzeugte Schnitte auswaehlen und ins 3D importieren:",
        wraplength=600,
        justify="left",
    ).pack(anchor="w", pady=(6, 6))

    list_frame = ttk.Frame(frame)
    list_frame.pack(fill="both", expand=True)

    listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.config(yscrollcommand=scrollbar.set)

    file_paths: list[str] = []

    status_var = tk.StringVar(value="")
    status_label = ttk.Label(frame, textvariable=status_var, wraplength=600, justify="left")
    status_label.pack(anchor="w", pady=(8, 0))

    def _refresh_list():
        listbox.delete(0, "end")
        file_paths.clear()
        try:
            from ifc_schnitt_importer.cadwork_api import project as uc
            from ifc_schnitt_importer.features.schnitt_importer.service import SchnittImporterService

            service = SchnittImporterService()
            project_3d_file_path = uc.get_3d_file_path()
            found = service.list_available_exchange_files(project_3d_file_path)
            for path in found:
                file_paths.append(path)
                listbox.insert("end", os.path.basename(path))

            if not found:
                status_var.set("Keine Zwischendateien gefunden - zuerst das externe Generator-Tool ausfuehren.")
            else:
                status_var.set(f"{len(found)} Zwischendatei(en) gefunden.")
        except Exception as e:
            status_var.set(f"Fehler beim Suchen der Zwischendateien: {e}")
            log_error_json(e, module=__name__, action="list_exchange_files", function_name="_refresh_list")

    def _run_import():
        selection = listbox.curselection()
        if not selection:
            status_var.set("Bitte mindestens einen Schnitt auswaehlen.")
            return

        try:
            from ifc_schnitt_importer.features.schnitt_importer.service import SchnittImporterService

            service = SchnittImporterService()
            summaries = []
            for index in selection:
                path = file_paths[index]
                ergebnis = service.load(path)
                result = service.import_schnitt(ergebnis)
                summary = (
                    f"{result.schnitt_name}: {result.erzeugte_flaechen} Flaechen, "
                    f"{result.erzeugte_linien} Linien erzeugt"
                    + (f", {result.ersetzte_alte_elemente} alte Elemente ersetzt" if result.ersetzte_alte_elemente else "")
                )
                if result.fehler:
                    summary += f"\n  {len(result.fehler)} Fehler:\n" + "\n".join(f"    - {f.beschreibung}" for f in result.fehler)
                summaries.append(summary)

            status_var.set("\n".join(summaries))
        except Exception as e:
            status_var.set(f"Fehler beim Import: {e}")
            log_error_json(e, module=__name__, action="import_schnitt", function_name="_run_import")
            import traceback

            traceback.print_exc()

    button_row = ttk.Frame(frame)
    button_row.pack(fill="x", pady=(10, 0))
    ttk.Button(button_row, text="Aktualisieren", command=_refresh_list).pack(side="left")
    ttk.Button(button_row, text="Ausgewaehlte importieren", command=_run_import).pack(side="left", padx=(8, 0))
    ttk.Button(button_row, text="Schliessen", command=root.destroy).pack(side="right")

    _refresh_list()

    if isinstance(root, tk.Tk):
        root.mainloop()
