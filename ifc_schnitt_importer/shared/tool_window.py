"""Fensterbasis wie im schaerholzbau Toolcenter (schlanke Kopie von shb_toolcenter.shared.tool_window).

Uebernimmt aus dem Toolcenter:

- Fenster anlegen (Tk oder Toplevel), Titel, Icon, Design (``shared/theme.py``)
- Grösse passend zur Windows-Skalierung, Position neben Cadwork, immer ganz auf dem Bildschirm
- dunkles Kopfband mit Titel/Untertitel und Knopf "Hilfe"
- Statuszeile mit Farbe je nach Zustand (``set_status``)
- Fusszeile: Statuszeile, Aktionsknöpfe, Hauptaktion farbig, "Schliessen" rot
- ``report_error``: loggen, Statuszeile, Meldung
- ``after``-Aufrufe, die beim Schliessen abgebrochen werden
- Schliessen wird während einer Verarbeitung verhindert (``is_processing``)

Bewusst ohne Toolcenter-Hauptmenue ("Zurück"), Element-Filter und
WindowConfig: das Plugin hat nur ein Fenster.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional, Tuple

from ifc_schnitt_importer.shared.logging import log_error_json
from ifc_schnitt_importer.shared.theme import (
    ERROR,
    MUTED,
    PAD,
    SUCCESS,
    WARNING,
    add_header_button,
    apply_theme,
    create_header,
    place_window,
    set_header,
)
from ifc_schnitt_importer.shared.window_geometry import get_window_geometry
from ifc_schnitt_importer.shared.window_utils import get_or_create_root

STATUS_COLORS = {"info": MUTED, "ok": SUCCESS, "warning": WARNING, "error": ERROR}
PRIMARY_BUTTON = "Primary.TButton"
DANGER_BUTTON = "Danger.TButton"

_ICON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "icon.png"))


class ToolWindow:
    """Basis fuer Fenster im Toolcenter-Stil; Unterklassen bauen ihre Oberflaeche nach ``super().__init__``."""

    TITLE = ""
    SUBTITLE = ""
    SIZE: Tuple[int, int] = (760, 640)      # bei 100 % Windows-Skalierung
    MIN_SIZE: Tuple[int, int] = (640, 520)
    BUSY_MESSAGE = "Verarbeitung läuft – bitte warten."

    def __init__(self, parent=None):
        self.parent = parent
        self.is_processing = False
        self._after_ids = set()
        self._status_label: Optional[ttk.Label] = None
        self.help_button: Optional[tk.Button] = None

        self.root = get_or_create_root(parent)
        apply_theme(self.root)
        self.root.title(self.TITLE)
        place_window(self.root, *self.SIZE, offset=get_window_geometry(), min_size=self.MIN_SIZE)
        self._set_icon()
        if parent is not None:
            self.root.transient(parent)
        self.root.columnconfigure(0, weight=1)
        self.header = create_header(self.root, self.TITLE, self.SUBTITLE)
        self.header.grid(row=0, column=0, sticky="ew")

        self.status_var = tk.StringVar(master=self.root, value="Bereit")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Destroy>", self._on_destroy, add="+")

    # ------------------------------------------------------------------ Aufbau
    def _set_icon(self) -> None:
        try:
            if os.path.isfile(_ICON_PATH):
                photo = tk.PhotoImage(master=self.root, file=_ICON_PATH)
                self.root._icon_photo = photo
                self.root.iconphoto(False, photo)
        except Exception as exc:  # ohne Icon geht es auch
            print(f"[ifc_schnitt_importer] Fenstericon nicht gesetzt: {exc}")

    def build_body(self, padding=PAD) -> ttk.Frame:
        body = ttk.Frame(self.root, padding=padding)
        body.grid(row=1, column=0, sticky="nsew")
        self.root.rowconfigure(1, weight=1)
        return body

    def set_header(self, title: str, subtitle: Optional[str] = None) -> None:
        set_header(self.header, title, self.SUBTITLE if subtitle is None else subtitle)

    def add_help_button(self, command: Callable) -> tk.Button:
        if self.help_button is None:
            self.help_button = add_header_button(self.header, "Hilfe", command)
        return self.help_button

    def build_status_label(self, parent) -> ttk.Label:
        self._status_label = ttk.Label(parent, textvariable=self.status_var, foreground=STATUS_COLORS["info"])
        return self._status_label

    def build_footer(self, parent, row: int, actions=(), primary: str = "", close_text: str = "Schliessen") -> dict:
        """Fusszeile mit Trennlinie: Statuszeile, darunter ``actions`` (Text, Befehl) rechts und "Schliessen".

        Liefert die Aktionsknoepfe nach Text, damit das Fenster sie sperren
        oder die Hauptaktion (``set_primary``) wechseln kann.
        """

        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(8, 0))
        ttk.Separator(frame).pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        self.build_status_label(frame).pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        ttk.Button(frame, text=close_text, command=self.close, style=DANGER_BUTTON).pack(side=tk.RIGHT, padx=(4, 0))
        buttons = {}
        for key, text, command in reversed(list(actions)):
            button = ttk.Button(frame, text=text, command=command, style=PRIMARY_BUTTON if key == primary else "TButton")
            button.pack(side=tk.RIGHT, padx=(4, 0))
            buttons[key] = button
        self.footer = frame
        return buttons

    @staticmethod
    def set_primary(buttons: dict, primary: Optional[str]) -> None:
        """Hauptaktion (farbig) auf den Knopf ``primary`` legen; None = keiner."""

        for key, button in buttons.items():
            try:
                button.configure(style=PRIMARY_BUTTON if key == primary else "TButton")
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ Status und Fehler
    def set_status(self, text: str, level: str = "info") -> None:
        self.status_var.set(text)
        if self._status_label is not None:
            try:
                self._status_label.configure(foreground=STATUS_COLORS.get(level, STATUS_COLORS["info"]))
            except tk.TclError:
                pass

    def report_error(self, exc: BaseException, action: str, message: Optional[str] = None, show: bool = True) -> None:
        text = message or "Fehler"
        print(f"[ifc_schnitt_importer] {text}: {exc}")
        log_error_json(exc, module=type(self).__module__, action=action, function_name=f"{type(self).__name__}.{action}")
        self.set_status(f"{text}: {exc}", "error")
        if show:
            self.show_error(f"{text}:\n{exc}\n\nDetails stehen in der Cadwork-Konsole.")

    def show_error(self, text: str) -> None:
        try:
            messagebox.showerror(self.TITLE, text, parent=self.root)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ Zeitgeber
    def after(self, delay_ms: int, callback: Callable, *args) -> str:
        """Wie ``root.after``; noch offene Aufrufe werden beim Schliessen abgebrochen."""

        after_id = None

        def _run():
            self._after_ids.discard(after_id)
            callback(*args)

        after_id = self.root.after(delay_ms, _run)
        self._after_ids.add(after_id)
        return after_id

    def _on_destroy(self, event) -> None:
        if event.widget is self.root:
            self._cancel_after_calls()

    def _cancel_after_calls(self) -> None:
        for after_id in list(self._after_ids):
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._after_ids.clear()

    # ------------------------------------------------------------------ Schliessen
    def can_close(self) -> bool:
        if self.is_processing:
            messagebox.showwarning("Bitte warten", self.BUSY_MESSAGE, parent=self.root)
            return False
        return True

    def on_close(self) -> None:
        """Hook fuer Unterklassen (z.B. Einstellungen speichern)."""

    def close(self, force: bool = False) -> None:
        if not force and not self.can_close():
            return
        try:
            self.on_close()
        except Exception as exc:
            log_error_json(exc, module=type(self).__module__, action="on_close")
        self._cancel_after_calls()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def show(self) -> None:
        """Blockiert, bis das Fenster zu ist (Tk: mainloop, Toplevel: wait_window)."""

        if isinstance(self.root, tk.Tk):
            self.root.mainloop()
        else:
            self.root.wait_window()
