"""UI window for the IFC Schnitt Importer.

STATUS: Etappe 1 placeholder - see docs/konzept.md.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ifc_schnitt_importer.app.config import AppConfig
from ifc_schnitt_importer.shared.window_utils import get_or_create_root


def show_schnitt_importer_window(parent=None):
    root = get_or_create_root(parent)
    root.title(f"{AppConfig.APP_NAME} - Schnitt Importer")
    root.geometry("560x360")

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="IFC Schnitt Importer",
        font=("TkDefaultFont", 12, "bold"),
    ).pack(anchor="w")

    ttk.Label(
        frame,
        text=(
            "Noch nicht implementiert (Etappe 4).\n\n"
            "Geplanter Ablauf:\n"
            "1. Zwischendatei(en) aus dem Schnitt-Generator waehlen\n"
            "2. Flaechen (Schnittflaechen) und Linien (Konturen) an\n"
            "   IFC-Originalposition im 3D erzeugen\n"
            "3. Vorherigen Import desselben Schnitts ersetzen"
        ),
        justify="left",
        wraplength=520,
    ).pack(anchor="w", pady=(12, 0))

    ttk.Button(frame, text="Schliessen", command=root.destroy).pack(anchor="e", pady=(20, 0))

    if isinstance(root, tk.Tk):
        root.mainloop()
