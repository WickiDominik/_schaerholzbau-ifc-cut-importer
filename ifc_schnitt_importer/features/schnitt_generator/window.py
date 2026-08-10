"""UI window for the IFC Schnitt Generator.

STATUS: Etappe 1 placeholder. Shows the planned workflow and current
implementation status so the plugin is already usable (as a preview) for
the Cadwork-side integration test, before Etappe 2/3 land the real logic.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ifc_schnitt_importer.app.config import AppConfig
from ifc_schnitt_importer.shared.window_utils import get_or_create_root


def show_schnitt_generator_window(parent=None):
    root = get_or_create_root(parent)
    root.title(f"{AppConfig.APP_NAME} - Schnitt Generator")
    root.geometry("560x420")

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="IFC Schnitt Generator",
        font=("TkDefaultFont", 12, "bold"),
    ).pack(anchor="w")

    ttk.Label(
        frame,
        text=(
            "Noch nicht implementiert (Etappe 2/3).\n\n"
            "Geplanter Ablauf:\n"
            "1. IFC-Datei waehlen (aus Archicad exportiert)\n"
            "2. Ausgabeelement(e)/Achsen im Modell waehlen, die die\n"
            "   Schnittlage definieren (horizontal und/oder vertikal)\n"
            "3. IFC wird ueber bim_controller importiert und je Schnitt\n"
            "   auf die gewaehlte Ebene reduziert\n"
            "4. Ergebnis wird als Zwischendatei gespeichert\n"
            f"   (siehe app/config.PathConfig.EXCHANGE_SUBDIRECTORY)"
        ),
        justify="left",
        wraplength=520,
    ).pack(anchor="w", pady=(12, 0))

    ttk.Button(frame, text="Schliessen", command=root.destroy).pack(anchor="e", pady=(20, 0))

    if isinstance(root, tk.Tk):
        root.mainloop()
