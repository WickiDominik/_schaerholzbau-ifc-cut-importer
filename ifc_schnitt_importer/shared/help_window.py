"""Hilfefenster wie im Toolcenter: zeigt docs/benutzerhandbuch.md neben dem Fenster (nicht modal)."""

from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import ttk

from ifc_schnitt_importer.shared.theme import ACCENT, FAMILY, FONT_FIXED, FONT_TITLE, SURFACE
from ifc_schnitt_importer.shared.tool_window import DANGER_BUTTON, ToolWindow

GUIDE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benutzerhandbuch.md"))

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def render_lines(markdown: str):
    """Markdown -> [(Art, Text)]: title, subtitle, code, bullet, text."""

    zeilen = []
    in_code = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            zeilen.append(("code", line))
            continue
        heading = _HEADING.match(line)
        if heading:
            zeilen.append(("title" if len(heading.group(1)) == 1 else "subtitle", heading.group(2)))
            continue
        line = line.replace("**", "").replace("`", "")
        if line.lstrip().startswith("- "):
            zeilen.append(("bullet", "•  " + line.lstrip()[2:]))
        elif line.startswith("  ") and zeilen and zeilen[-1][0] == "bullet":
            zeilen[-1] = ("bullet", zeilen[-1][1] + " " + line.strip())   # Fortsetzung der Aufzaehlung
        elif line and zeilen and zeilen[-1][0] == "text" and zeilen[-1][1]:
            zeilen[-1] = ("text", zeilen[-1][1] + " " + line.strip())     # Absatz zusammenfuegen
        else:
            zeilen.append(("text", line))
    return zeilen


class HelpWindow(ToolWindow):
    SIZE = (620, 640)
    MIN_SIZE = (420, 360)

    def __init__(self, parent, title: str):
        self.TITLE = title
        super().__init__(parent)
        main = self.build_body()
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        text = tk.Text(main, wrap="word", padx=12, pady=8, relief="flat", cursor="arrow", background=SURFACE)
        scroll = ttk.Scrollbar(main, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        text.tag_configure("title", font=FONT_TITLE, foreground=ACCENT, spacing3=6)
        text.tag_configure("subtitle", font=(FAMILY, 11, "bold"), foreground=ACCENT, spacing1=10, spacing3=4)
        text.tag_configure("code", font=FONT_FIXED, lmargin1=12, lmargin2=12)
        text.tag_configure("bullet", lmargin1=12, lmargin2=26)

        try:
            with open(GUIDE_FILE, encoding="utf-8") as handle:
                markdown = handle.read()
        except OSError as exc:
            markdown = f"# Hilfe\n\nAnleitung nicht gefunden: {GUIDE_FILE}\n({exc})"
        for kind, line in render_lines(markdown):
            text.insert("end", line + "\n", (kind,))
        text.configure(state="disabled")

        footer = ttk.Frame(main)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Separator(footer).pack(side=tk.TOP, fill=tk.X, pady=(0, 8))
        ttk.Button(footer, text="Schliessen", command=self.close, style=DANGER_BUTTON).pack(side=tk.RIGHT)


def show_help(parent, title: str) -> HelpWindow:
    """Oeffnet die Hilfe neben dem Fenster und kehrt sofort zurueck."""

    return HelpWindow(parent, title)
