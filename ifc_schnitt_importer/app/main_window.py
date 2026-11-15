"""Hauptfenster "IFC-Schnitte": gefuehrter Ablauf Definieren -> Generieren -> Importieren.

Aussehen und Bedienung wie im schaerholzbau Toolcenter (Kopfband, Hilfe,
Statuszeile, Fusszeile mit farbiger Hauptaktion, siehe
shared/tool_window.py und shared/theme.py).

Aufbau von oben nach unten:

- Schrittleiste: 1 Schnitte definieren > 2 Aus IFC generieren > 3 Ins 3D
  importieren, mit Hinweis, was als Naechstes zu tun ist
- Projekt & IFC: Projektnummer, Ablage (Ordner oeffnen), IFC-Datei (wird
  pro 3D-Datei gemerkt)
- Schnitte: eine Zeile je Schnitt mit Status (fehlerhaft, noch nicht
  generiert, IFC neuer, bereit, im 3D); Haekchen = wird importiert
- Fusszeile: "Schnitte generieren" und "Importieren"; der Knopf fuer den
  naechsten Schritt ist farbig. Optional wird nach dem Generieren direkt
  importiert.

Threading-Modell (unveraendert, siehe schnitt_generator/service.py):
- Cadwork-API-Aufrufe (ec.*/ac.*/vc.*/uc.*) NUR auf dem Tk-Hauptthread
  (Cadwork ist single-threaded): Uebersicht lesen, Definitionen
  exportieren, Importieren.
- Nur der generator_tool-Subprozess (keine Cadwork-API) laeuft in einem
  Hintergrund-Thread; seine Ausgabe kommt ueber eine Queue zurueck und
  wird per ``after``-Polling auf dem Hauptthread verarbeitet.
- Der Import laeuft synchron auf dem Hauptthread, mit
  ``update_idletasks()`` fuer die Fortschrittsanzeige (wie im Toolcenter).
"""

from __future__ import annotations

import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from ifc_schnitt_importer.app.config import AppConfig, GeneratorToolConfig, PathConfig, SchnittDefinitionConfig
from ifc_schnitt_importer.features.schnitt_workflow import uebersicht as ub
from ifc_schnitt_importer.shared.local_settings import load_value, save_value
from ifc_schnitt_importer.shared.logging import log_error_json
from ifc_schnitt_importer.shared.theme import (
    BORDER,
    BUTTON_VARIANTS,
    FONT_BOLD,
    FONT_HINT,
    FONT_ITALIC,
    FONT_SMALL,
    MUTED,
    ROW_ERROR_BG,
    ROW_WARNING_BG,
    SUCCESS,
    SURFACE,
    TEXT,
)
from ifc_schnitt_importer.shared.tool_window import ToolWindow

_SETTINGS_FILE = GeneratorToolConfig.LAST_IFC_PATH_SETTINGS_FILE
_LAST_IFC_KEY = "last_ifc_path"            # zuletzt gewaehlte IFC (alle Projekte)
_IFC_PRO_PROJEKT_KEY = "ifc_pro_projekt"   # 3D-Datei -> IFC-Datei
_DIREKT_IMPORTIEREN_KEY = "direkt_importieren"

# Anteil des Fortschrittsbalkens fuers Laden der IFC-Bauteile (der
# langsamste Teil) vs. die anschliessende Schnittberechnung.
_LADE_ANTEIL_PROZENT = 90

_GENERATOR_LINE_PATTERNS = (
    re.compile(r"(\d+)\s+Kandidaten-Elemente"),
    re.compile(r"\.\.\.\s*(\d+)/(\d+)\s+geprueft"),
    re.compile(r"^\s*->\s*(.+?):\s*(\d+)\s+Flaechen,\s*(\d+)\s+Linien"),
)

CHECKED = "☑"
UNCHECKED = "☐"

_ZEILEN_TAGS = {
    ub.FEHLER: "fehler",
    ub.NICHT_GENERIERT: "offen",
    ub.VERALTET: "offen",
    ub.IM_3D: "fertig",
}

_SCHRITT_FARBEN = {
    # Zustand: (Hintergrund, Schrift)
    ub.ERLEDIGT: (SUCCESS, "#ffffff"),
    ub.AKTIV: (BUTTON_VARIANTS["primary"][0], "#ffffff"),
    ub.OFFEN: (BUTTON_VARIANTS["secondary"][0], MUTED),
}

_GENERIEREN = "generieren"
_IMPORTIEREN = "importieren"


class SchnittWorkflowWindow(ToolWindow):
    TITLE = AppConfig.APP_NAME
    SUBTITLE = "Schnitte aus der IFC des Architekten berechnen und als Referenz ins 3D-Modell übernehmen"
    SIZE = (820, 720)
    MIN_SIZE = (700, 600)
    BUSY_MESSAGE = "Die Schnitte werden noch verarbeitet. Bitte warten, bis der Vorgang abgeschlossen ist."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.uebersicht = ub.Uebersicht()
        self.auswahl: set = set()                # Schluessel der angehakten Zeilen
        self.ergebnisse: Dict[str, str] = {}     # Schluessel -> Ergebnis des letzten Laufs
        self.project_3d_file_path = ""
        self.projekt_nummer = ""

        self.ifc_path = tk.StringVar(master=self.root)
        self.ifc_info = tk.StringVar(master=self.root)
        self.direkt_importieren = tk.BooleanVar(
            master=self.root, value=bool(load_value(_SETTINGS_FILE, _DIREKT_IMPORTIEREN_KEY, True))
        )
        self.hinweis = tk.StringVar(master=self.root)
        self.projekt_text = tk.StringVar(master=self.root, value="–")
        self.ablage_text = tk.StringVar(master=self.root, value="–")
        self.progress_var = tk.DoubleVar(master=self.root)
        self.progress_message = tk.StringVar(master=self.root)

        self._build_ui()
        self.ifc_path.trace_add("write", lambda *_: self._ifc_geaendert())
        self._ifc_geaendert()
        self.set_status("Lese Schnitte aus dem Modell …")
        self.after(50, self.aktualisieren)

    # ------------------------------------------------------------------ Aufbau
    def _build_ui(self) -> None:
        self.add_help_button(self._zeige_hilfe)
        main = self.build_body()
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self._build_schrittleiste(main)
        self._build_projekt(main)
        self._build_tabelle(main)
        self._build_fortschritt(main)

        optionen = ttk.Frame(main)
        optionen.grid(row=4, column=0, sticky="ew")
        ttk.Checkbutton(
            optionen,
            text="Nach dem Generieren die neuen Schnitte direkt importieren",
            variable=self.direkt_importieren,
        ).pack(side=tk.LEFT)

        self.buttons = self.build_footer(
            main,
            row=5,
            actions=(
                (_GENERIEREN, "Schnitte generieren", self.generieren),
                (_IMPORTIEREN, "Importieren", self.importieren),
            ),
            primary=_GENERIEREN,
        )

    def _build_schrittleiste(self, parent) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        leiste = tk.Frame(frame, bg=BORDER)
        leiste.pack(fill=tk.X)
        self.schritt_labels: Dict[str, tk.Label] = {}
        for index, (schluessel, titel) in enumerate(ub.SCHRITTE):
            leiste.columnconfigure(index, weight=1, uniform="schritt")
            label = tk.Label(leiste, text=f"{index + 1}  {titel}", font=FONT_BOLD, padx=10, pady=6)
            label.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 1, 0))
            self.schritt_labels[schluessel] = label
        self.hinweis_label = tk.Label(
            frame, textvariable=self.hinweis, bg=SURFACE, fg=TEXT, font=FONT_ITALIC, anchor="w", justify="left",
            padx=10, pady=6, highlightthickness=1, highlightbackground=BORDER,
        )
        self.hinweis_label.pack(fill=tk.X)
        frame.bind("<Configure>", lambda e: self.hinweis_label.configure(wraplength=max(200, e.width - 24)))

    def _build_projekt(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text="Projekt und IFC", padding=8)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Projekt:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(frame, textvariable=self.projekt_text, font=FONT_BOLD).grid(row=0, column=1, sticky="w")

        ttk.Label(frame, text="Ablage:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(2, 0))
        ttk.Label(frame, textvariable=self.ablage_text, font=FONT_SMALL, foreground=MUTED).grid(
            row=1, column=1, sticky="w", pady=(2, 0))
        self.ablage_button = ttk.Button(frame, text="Ordner öffnen", command=self._ablage_oeffnen)
        self.ablage_button.grid(row=1, column=2, sticky="e", padx=(6, 0), pady=(2, 0))

        ttk.Label(frame, text="IFC-Datei:").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(8, 0))
        self.ifc_entry = ttk.Entry(frame, textvariable=self.ifc_path)
        self.ifc_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        self.ifc_button = ttk.Button(frame, text="Durchsuchen …", command=self._ifc_waehlen)
        self.ifc_button.grid(row=2, column=2, sticky="e", padx=(6, 0), pady=(8, 0))
        ttk.Label(frame, textvariable=self.ifc_info, font=FONT_HINT, foreground=MUTED).grid(
            row=3, column=1, columnspan=2, sticky="w")

    def _build_tabelle(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text="Schnitte", padding=8)
        frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        werkzeuge = ttk.Frame(frame)
        werkzeuge.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.alle_button = ttk.Button(werkzeuge, text="Alle", command=lambda: self._alle_waehlen(True))
        self.alle_button.pack(side=tk.LEFT)
        self.keine_button = ttk.Button(werkzeuge, text="Keine", command=lambda: self._alle_waehlen(False))
        self.keine_button.pack(side=tk.LEFT, padx=(4, 0))
        self.zaehler_label = ttk.Label(werkzeuge, text="", foreground=MUTED, font=FONT_SMALL)
        self.zaehler_label.pack(side=tk.LEFT, padx=(10, 0))
        self.aktualisieren_button = ttk.Button(werkzeuge, text="Aktualisieren", command=self.aktualisieren)
        self.aktualisieren_button.pack(side=tk.RIGHT)

        spalten = (
            ("auswahl", "", 34, "center", False),
            ("name", "Schnitt", 150, "w", True),
            ("typ", "Typ", 80, "w", False),
            ("ebene", "Lage", 140, "w", True),
            ("generiert", "Generiert", 122, "w", False),
            ("status", "Status", 230, "w", True),
        )
        self.tree = ttk.Treeview(frame, columns=[s[0] for s in spalten], show="headings", selectmode="none", height=10)
        for key, text, breite, anchor, stretch in spalten:
            self.tree.heading(key, text=text, anchor=anchor)
            self.tree.column(key, width=breite, minwidth=breite if key == "auswahl" else 60, anchor=anchor, stretch=stretch)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.tag_configure("fehler", background=ROW_ERROR_BG)
        self.tree.tag_configure("offen", background=ROW_WARNING_BG)
        self.tree.tag_configure("fertig", foreground=SUCCESS)
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        ttk.Label(
            frame,
            text="Häkchen = wird importiert (ersetzt einen früheren Import desselben Schnitts). "
                 "Doppelklick auf eine Zeile zeigt Details.",
            font=FONT_HINT, foreground=MUTED,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_fortschritt(self, parent) -> None:
        self.progress_frame = ttk.LabelFrame(parent, text="Fortschritt", padding=8)
        self.progress_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.progress_frame.columnconfigure(0, weight=1)
        ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100).grid(
            row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(self.progress_frame, textvariable=self.progress_message, font=FONT_ITALIC).grid(
            row=1, column=0, sticky="w")
        self.progress_frame.grid_remove()

    # ------------------------------------------------------------------ Daten lesen (Hauptthread, Cadwork-API)
    def aktualisieren(self, auswahl: Optional[List[str]] = None) -> None:
        """Modell, Ablage und Importe neu lesen und die Tabelle fuellen.

        ``auswahl``: diese Zeilen anhaken (z.B. frisch generierte), sonst
        die Standard-Auswahl (alle, die bereit zum Import sind).
        """

        from ifc_schnitt_importer.cadwork_api import project as uc
        from ifc_schnitt_importer.features.schnitt_generator.service import SchnittGeneratorService
        from ifc_schnitt_importer.features.schnitt_importer.service import SchnittImporterService

        self.set_status("Lese Schnitte aus dem Modell …")
        self.root.update_idletasks()
        try:
            self.project_3d_file_path = uc.get_3d_file_path() or ""
            self.projekt_nummer = uc.get_project_number() or ""
            definitionen = SchnittGeneratorService().scan_schnitt_definitionen()
            importer = SchnittImporterService()
            dateien = importer.list_available_exchange_files(self.project_3d_file_path) if self.project_3d_file_path else []
            importierte = importer.importierte_schnitt_namen()
        except Exception as exc:
            self.report_error(exc, "aktualisieren", "Schnitte konnten nicht gelesen werden")
            return

        self._lade_ifc_fuer_projekt()
        self.uebersicht = ub.baue_uebersicht(
            definitionen.definitionen,
            definitionen.fehler,
            dateien,
            importierte,
            self.projekt_nummer,
            datei_suffix=PathConfig.EXCHANGE_FILE_SUFFIX,
            ifc_geaendert_am=self._ifc_mtime(),
        )
        gueltig = {z.schluessel for z in self.uebersicht.zeilen if z.importierbar}
        self.auswahl = set(auswahl if auswahl is not None else ub.standard_auswahl(self.uebersicht)) & gueltig
        self.ergebnisse = {k: v for k, v in self.ergebnisse.items() if self.uebersicht.zeile(k) is not None}

        self._projekt_anzeigen()
        self._tabelle_fuellen()
        self._ablauf_anzeigen()

        anzahl = self.uebersicht.anzahl_definitionen
        fehler = len(self.uebersicht.mit_status(ub.FEHLER))
        text = f"{anzahl} Schnitt-Definition(en) im Modell"
        if fehler:
            self.set_status(f"{text}, {fehler} fehlerhaft – Doppelklick auf die rote Zeile zeigt den Grund", "warning")
        else:
            self.set_status(text)

    def _projekt_anzeigen(self) -> None:
        if not self.project_3d_file_path:
            self.projekt_text.set(self.projekt_nummer or "–")
            self.ablage_text.set("3D-Datei ist noch nicht gespeichert – bitte zuerst speichern")
            return
        self.projekt_text.set(f"{self.projekt_nummer or '(ohne Nummer)'}  ·  {os.path.basename(self.project_3d_file_path)}")
        self.ablage_text.set(PathConfig.get_exchange_directory(self.project_3d_file_path))

    def _tabelle_fuellen(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for zeile in self.uebersicht.zeilen:
            self.tree.insert("", "end", iid=zeile.schluessel, values=self._zeilen_werte(zeile),
                             tags=(_ZEILEN_TAGS.get(zeile.status, ""),))
        self._auswahl_anzeigen()

    def _zeilen_werte(self, zeile: ub.SchnittZeile):
        if zeile.importierbar:
            haken = CHECKED if zeile.schluessel in self.auswahl else UNCHECKED
        else:
            haken = ""
        status = zeile.status_text
        if zeile.status == ub.FEHLER:
            status = f"{status}: {zeile.meldung}"
        elif zeile.status != ub.IM_3D and zeile.im_3d:
            status = f"{status} (älterer Stand im 3D)"
        ergebnis = self.ergebnisse.get(zeile.schluessel)
        if ergebnis:
            status = f"{status} – {ergebnis}"
        return (haken, zeile.name, zeile.typ, zeile.ebene, ub.zeit_text(zeile.generiert_am), status)

    def _auswahl_anzeigen(self) -> None:
        for zeile in self.uebersicht.zeilen:
            if self.tree.exists(zeile.schluessel):
                self.tree.item(zeile.schluessel, values=self._zeilen_werte(zeile))
        anzahl = len(self.auswahl)
        importierbar = len([z for z in self.uebersicht.zeilen if z.importierbar])
        self.zaehler_label.configure(text=f"{anzahl} von {importierbar} zum Import gewählt" if importierbar else "")
        self.buttons[_IMPORTIEREN].configure(text=f"Importieren ({anzahl})" if anzahl else "Importieren")
        self._knoepfe_freigeben()

    def _ablauf_anzeigen(self) -> None:
        schritt = ub.naechster_schritt(self.uebersicht, ifc_gewaehlt=self._ifc_gueltig())
        if not self.project_3d_file_path:
            hinweis = "Die 3D-Datei ist noch nicht gespeichert. Bitte zuerst speichern, dann «Aktualisieren»."
        else:
            hinweis = ub.HINWEISE[schritt]
            fehler = len(self.uebersicht.mit_status(ub.FEHLER))
            if fehler and schritt != ub.SCHRITT_DEFINIEREN:
                hinweis += f" {fehler} Definition(en) fehlerhaft (rot) – Doppelklick zeigt den Grund."
        self.hinweis.set(hinweis)
        for key, zustand in ub.schritt_zustaende(schritt).items():
            bg, fg = _SCHRITT_FARBEN[zustand]
            label = self.schritt_labels[key]
            titel = label.cget("text").lstrip("✓ ")
            label.configure(bg=bg, fg=fg, text=f"✓ {titel}" if zustand == ub.ERLEDIGT else titel)
        primary = {
            ub.SCHRITT_GENERIEREN: _GENERIEREN,
            ub.SCHRITT_IFC_WAEHLEN: _GENERIEREN,
            ub.SCHRITT_IMPORTIEREN: _IMPORTIEREN,
        }.get(schritt)
        self.set_primary(self.buttons, primary)
        if schritt == ub.SCHRITT_IFC_WAEHLEN:
            self.ifc_entry.focus_set()

    def _knoepfe_freigeben(self) -> None:
        bereit = not self.is_processing
        projekt_ok = bool(self.project_3d_file_path)
        zustaende = {
            _GENERIEREN: bereit and projekt_ok and self.uebersicht.anzahl_definitionen > 0,
            _IMPORTIEREN: bereit and bool(self.auswahl),
        }
        for key, aktiv in zustaende.items():
            self.buttons[key].configure(state=tk.NORMAL if aktiv else tk.DISABLED)
        for widget in (self.aktualisieren_button, self.alle_button, self.keine_button, self.ifc_button, self.ablage_button):
            widget.configure(state=tk.NORMAL if bereit else tk.DISABLED)
        self.ifc_entry.configure(state=tk.NORMAL if bereit else tk.DISABLED)

    # ------------------------------------------------------------------ IFC
    def _ifc_gueltig(self) -> bool:
        pfad = self.ifc_path.get().strip()
        return bool(pfad) and os.path.isfile(pfad)

    def _ifc_mtime(self) -> Optional[float]:
        if not self._ifc_gueltig():
            return None
        try:
            return os.path.getmtime(self.ifc_path.get().strip())
        except OSError:
            return None

    def _lade_ifc_fuer_projekt(self) -> None:
        """IFC dieses Projekts (pro 3D-Datei gemerkt), sonst die zuletzt gewaehlte."""

        if self.ifc_path.get().strip():
            return
        pro_projekt = load_value(_SETTINGS_FILE, _IFC_PRO_PROJEKT_KEY, {}) or {}
        pfad = pro_projekt.get(self.project_3d_file_path) if isinstance(pro_projekt, dict) else None
        if not pfad:
            pfad = load_value(_SETTINGS_FILE, _LAST_IFC_KEY, "")
        if pfad:
            self.ifc_path.set(pfad)

    def _ifc_merken(self, pfad: str) -> None:
        save_value(_SETTINGS_FILE, _LAST_IFC_KEY, pfad)
        if self.project_3d_file_path:
            pro_projekt = load_value(_SETTINGS_FILE, _IFC_PRO_PROJEKT_KEY, {}) or {}
            if not isinstance(pro_projekt, dict):
                pro_projekt = {}
            pro_projekt[self.project_3d_file_path] = pfad
            save_value(_SETTINGS_FILE, _IFC_PRO_PROJEKT_KEY, pro_projekt)

    def _ifc_waehlen(self) -> None:
        aktuell = self.ifc_path.get().strip()
        start = os.path.dirname(aktuell) if aktuell else (os.path.dirname(self.project_3d_file_path) or None)
        pfad = filedialog.askopenfilename(
            title="IFC-Datei des Architekten wählen",
            filetypes=[("IFC-Dateien", "*.ifc"), ("Alle Dateien", "*.*")],
            initialdir=start,
            parent=self.root,
        )
        if pfad:
            self.ifc_path.set(os.path.normpath(pfad))
            self._ifc_merken(self.ifc_path.get())

    def _ifc_geaendert(self) -> None:
        pfad = self.ifc_path.get().strip()
        if not pfad:
            self.ifc_info.set("Noch keine IFC-Datei gewählt.")
        elif not os.path.isfile(pfad):
            self.ifc_info.set("Datei nicht gefunden.")
        else:
            try:
                groesse_mb = os.path.getsize(pfad) / (1024 * 1024)
                self.ifc_info.set(f"Stand {ub.zeit_text(os.path.getmtime(pfad))}  ·  {groesse_mb:.1f} MB")
            except OSError:
                self.ifc_info.set("")
        # Status "IFC ist neuer" haengt von der gewaehlten IFC ab - ohne
        # Cadwork neu zu lesen nur die Dateizeiten neu vergleichen.
        if self.uebersicht.zeilen and not self.is_processing:
            self._status_neu_bewerten()

    def _status_neu_bewerten(self) -> None:
        ifc_mtime = self._ifc_mtime()
        for zeile in self.uebersicht.zeilen:
            if zeile.status not in (ub.BEREIT, ub.IM_3D, ub.VERALTET) or zeile.generiert_am is None:
                continue
            if ifc_mtime is not None and zeile.generiert_am < ifc_mtime:
                zeile.status = ub.VERALTET
            else:
                zeile.status = ub.IM_3D if zeile.im_3d else ub.BEREIT
            if self.tree.exists(zeile.schluessel):
                self.tree.item(zeile.schluessel, tags=(_ZEILEN_TAGS.get(zeile.status, ""),))
        self._auswahl_anzeigen()
        self._ablauf_anzeigen()

    # ------------------------------------------------------------------ Tabelle bedienen
    def _on_tree_click(self, event) -> str:
        if self.is_processing:
            return "break"
        schluessel = self.tree.identify_row(event.y)
        zeile = self.uebersicht.zeile(schluessel) if schluessel else None
        if zeile is None or not zeile.importierbar:
            return "break"
        if schluessel in self.auswahl:
            self.auswahl.discard(schluessel)
        else:
            self.auswahl.add(schluessel)
        self._auswahl_anzeigen()
        return "break"

    def _on_tree_double_click(self, event) -> str:
        schluessel = self.tree.identify_row(event.y)
        zeile = self.uebersicht.zeile(schluessel) if schluessel else None
        if zeile is None:
            return "break"
        # Der erste Klick des Doppelklicks hat das Haekchen umgeschaltet - zuruecknehmen.
        self._on_tree_click(event)
        zeilen = [f"Schnitt: {zeile.name}", f"Status: {zeile.status_text}"]
        if zeile.meldung:
            zeilen.append(f"Fehler: {zeile.meldung}")
        if zeile.element_id is not None:
            zeilen.append(f"Element-ID mit der Definition: {zeile.element_id} "
                          f"(Benutzerattribute {SchnittDefinitionConfig.ATTRIBUTE_NUMBER}–"
                          f"{SchnittDefinitionConfig.ATTRIBUTE_NUMBER + SchnittDefinitionConfig.MAX_DEFINITIONEN_PRO_ELEMENT - 1})")
        if zeile.ebene:
            zeilen.append(f"Lage: {zeile.ebene}")
        if zeile.datei:
            zeilen.append(f"Zwischendatei: {zeile.datei}")
            zeilen.append(f"Generiert: {ub.zeit_text(zeile.generiert_am)}")
        zeilen.append(f"Im 3D: {'ja' if zeile.im_3d else 'nein'}")
        if zeile.schluessel in self.ergebnisse:
            zeilen.append(f"Letzter Lauf: {self.ergebnisse[zeile.schluessel]}")
        messagebox.showinfo(zeile.name, "\n".join(zeilen), parent=self.root)
        return "break"

    def _alle_waehlen(self, alle: bool) -> None:
        if alle:
            self.auswahl = {z.schluessel for z in self.uebersicht.zeilen if z.importierbar}
        else:
            self.auswahl = set()
        self._auswahl_anzeigen()

    def _ablage_oeffnen(self) -> None:
        if not self.project_3d_file_path:
            return
        ordner = PathConfig.get_exchange_directory(self.project_3d_file_path)
        try:
            os.makedirs(ordner, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(ordner)  # noqa: S606 - Explorer oeffnen
            else:
                self.set_status(f"Ablage: {ordner}")
        except OSError as exc:
            self.report_error(exc, "ablage_oeffnen", "Ordner konnte nicht geöffnet werden")

    # ------------------------------------------------------------------ Verarbeitung (gemeinsam)
    def _start(self, titel: str) -> None:
        self.is_processing = True
        self._knoepfe_freigeben()
        self.progress_frame.configure(text=titel)
        self.progress_frame.grid()
        self.progress_var.set(0)
        self.progress_message.set("Starte …")
        self.root.update_idletasks()

    def _ende(self) -> None:
        self.is_processing = False
        self.progress_frame.grid_remove()
        self.progress_var.set(0)
        self.progress_message.set("")
        self._knoepfe_freigeben()

    def _fortschritt(self, prozent: float, text: Optional[str] = None) -> None:
        self.progress_var.set(max(0.0, min(100.0, prozent)))
        if text is not None:
            self.progress_message.set(text)

    # ------------------------------------------------------------------ Schritt 2: Generieren
    def generieren(self) -> None:
        if self.is_processing:
            return
        from ifc_schnitt_importer.features.schnitt_generator.service import SchnittGeneratorService

        if not self._ifc_gueltig():
            if not self.ifc_path.get().strip():
                self._ifc_waehlen()
            if not self._ifc_gueltig():
                self.set_status("Bitte zuerst eine gültige IFC-Datei wählen.", "warning")
                return

        service = SchnittGeneratorService()
        if not service.generator_tool_verfuegbar():
            self.set_status("Generator-Tool ist nicht eingerichtet – siehe Meldung.", "error")
            messagebox.showerror(
                "Generator-Tool fehlt",
                "Das externe Generator-Tool ist auf diesem Rechner noch nicht eingerichtet.\n\n"
                "Einmalig einrichten (siehe generator_tool/README.md):\n"
                "  cd generator_tool\n"
                "  python -m venv .venv\n"
                "  .venv\\Scripts\\pip install -r requirements.txt",
                parent=self.root,
            )
            return

        ifc_datei = self.ifc_path.get().strip()
        self._ifc_merken(ifc_datei)
        self._start("Schnitte generieren")
        self.set_status("Schnitte werden generiert – das kann bei grossen IFC einige Minuten dauern", "warning")
        self.progress_message.set("Exportiere Schnitt-Definitionen …")
        self.root.update_idletasks()

        # Cadwork-API - Hauptthread.
        try:
            service.ensure_attribute_label()
            kontext = service.projekt_kontext()
            export, definitionen_datei = service.export_schnitt_definitionen(kontext)
        except Exception as exc:
            self._ende()
            self.report_error(exc, "export_schnitt_definitionen", "Schnitt-Definitionen konnten nicht exportiert werden")
            return

        if not export.definitionen:
            self._ende()
            self.set_status("Keine gültigen Schnitt-Definitionen im Modell.", "warning")
            self.aktualisieren()
            return

        self.progress_message.set(f"{len(export.definitionen)} Schnitt(e) – starte Generator …")
        self._generator_starten(service, ifc_datei, export, definitionen_datei, kontext)

    def _generator_starten(self, service, ifc_datei, export, definitionen_datei, kontext) -> None:
        # Der Subprozess beruehrt keine Cadwork-API -> Hintergrund-Thread,
        # damit Cadwork waehrend der Verarbeitung ansprechbar bleibt.
        line_queue: "queue.Queue" = queue.Queue()
        result_holder: dict = {}

        def _worker():
            try:
                result_holder["result"] = service.generate_schnitte(
                    ifc_datei, export, definitionen_datei, kontext,
                    line_callback=lambda line: line_queue.put(("line", line)),
                )
            except Exception as exc:  # noqa: BLE001 - wird im Hauptthread gemeldet
                result_holder["error"] = exc
            line_queue.put(("done", None))

        threading.Thread(target=_worker, daemon=True).start()

        def _poll():
            try:
                if not self.root.winfo_exists():
                    return
            except tk.TclError:
                return
            try:
                while True:
                    kind, payload = line_queue.get_nowait()
                    if kind == "line":
                        self._generator_zeile(payload)
                    else:
                        self._generieren_fertig(result_holder, export)
                        return
            except queue.Empty:
                pass
            self.after(100, _poll)

        self.after(100, _poll)

    def _generator_zeile(self, line: str) -> None:
        m = _GENERATOR_LINE_PATTERNS[1].search(line)
        if m:
            current, total = int(m.group(1)), int(m.group(2))
            if total:
                self._fortschritt(current / total * _LADE_ANTEIL_PROZENT, f"Lade IFC-Bauteile … {current}/{total}")
            return
        m = _GENERATOR_LINE_PATTERNS[0].search(line)
        if m:
            self._fortschritt(self.progress_var.get(), f"Lade {m.group(1)} Bauteile aus der IFC …")
            return
        m = _GENERATOR_LINE_PATTERNS[2].match(line)
        if m:
            self._fortschritt(min(99.0, max(self.progress_var.get(), _LADE_ANTEIL_PROZENT) + 2),
                              f"Schnitt «{m.group(1)}» berechnet: {m.group(2)} Flächen, {m.group(3)} Linien")

    def _generieren_fertig(self, result_holder: dict, export) -> None:
        from ifc_schnitt_importer.features.schnitt_generator.service import GeneratorToolNichtEingerichtetError

        self._ende()
        if "error" in result_holder:
            exc = result_holder["error"]
            if isinstance(exc, GeneratorToolNichtEingerichtetError):
                self.set_status("Generator-Tool ist nicht eingerichtet.", "error")
                self.show_error(str(exc))
            else:
                self.report_error(exc, "generate_schnitte", "Generierung fehlgeschlagen")
            return

        result = result_holder["result"]
        if not result.subprocess_erfolgreich:
            self.set_status("Generierung fehlgeschlagen – Details in der Cadwork-Konsole.", "error")
            self.show_error("Die Generierung ist fehlgeschlagen.\n\nDetails stehen in der Cadwork-Konsole.")
            self.aktualisieren()
            return

        erzeugt = {os.path.normcase(os.path.abspath(p)) for p in result.erzeugte_dateien}
        self.aktualisieren(auswahl=[])
        neue = [z.schluessel for z in self.uebersicht.zeilen
                if z.datei and os.path.normcase(os.path.abspath(z.datei)) in erzeugt]
        for schluessel in neue:
            self.ergebnisse[schluessel] = "neu generiert"
        self.auswahl = set(neue)
        self._auswahl_anzeigen()

        fehlend = len(export.definitionen) - len(neue)
        text = f"{len(neue)} von {len(export.definitionen)} Schnitt(en) generiert"
        if fehlend > 0:
            self.set_status(f"{text} – {fehlend} ohne Ergebnis, siehe Cadwork-Konsole", "warning")
        else:
            self.set_status(text, "ok")

        if neue and self.direkt_importieren.get():
            self.after(50, self.importieren, False)

    # ------------------------------------------------------------------ Schritt 3: Importieren
    def importieren(self, nachfragen: bool = True) -> None:
        if self.is_processing:
            return
        zeilen = [z for z in self.uebersicht.zeilen if z.schluessel in self.auswahl and z.importierbar]
        if not zeilen:
            self.set_status("Bitte mindestens einen Schnitt anhaken.", "warning")
            return

        veraltet = [z.name for z in zeilen if z.status == ub.VERALTET]
        if nachfragen and veraltet:
            if not messagebox.askyesno(
                "Älterer Stand",
                "Diese Schnitte wurden aus einer älteren IFC generiert:\n\n  "
                + "\n  ".join(veraltet)
                + "\n\nTrotzdem importieren? (Sonst zuerst «Schnitte generieren».)",
                parent=self.root,
            ):
                return

        from ifc_schnitt_importer.features.schnitt_importer.service import SchnittImporterService

        self._start("Schnitte importieren")
        self.set_status("Schnitte werden ins 3D importiert – bitte nicht unterbrechen", "warning")
        service = SchnittImporterService()
        fehlerhafte: List[str] = []

        # Im Hauptthread: die Cadwork-API vertraegt keine Aufrufe aus Hintergrund-Threads.
        for index, zeile in enumerate(zeilen):
            basis = index / len(zeilen) * 100
            anteil = 100 / len(zeilen)

            def _progress(current, total, message, basis=basis, anteil=anteil, name=zeile.name):
                fertig = (current / total) if total else 0
                self._fortschritt(basis + fertig * anteil, f"{name} ({index + 1}/{len(zeilen)}): {message}")
                self.root.update_idletasks()

            try:
                ergebnis = service.load(zeile.datei)
                result = service.import_schnitt(ergebnis, progress_callback=_progress)
                text = f"{result.erzeugte_flaechen} Flächen"
                if result.erzeugte_linien:
                    text += f", {result.erzeugte_linien} Linien"
                if result.ersetzte_alte_elemente:
                    text += ", alter Import ersetzt"
                if result.erzeugte_flaechen >= 2 and not result.flaechen_verbunden:
                    text += ", Flächen NICHT verbunden"
                if result.fehler:
                    text += f", {len(result.fehler)} Fehler"
                    fehlerhafte.append(f"{zeile.name}: {len(result.fehler)} Fehler (siehe Konsole)")
                self.ergebnisse[zeile.schluessel] = f"importiert: {text}"
            except Exception as exc:
                self.ergebnisse[zeile.schluessel] = f"Import fehlgeschlagen: {exc}"
                fehlerhafte.append(f"{zeile.name}: {exc}")
                print(f"[main_window] Fehler beim Import von {zeile.datei}: {exc}")
                log_error_json(exc, module=__name__, action="import_schnitt", function_name="importieren")

        self._ende()
        self.aktualisieren(auswahl=[])
        if fehlerhafte:
            self.set_status(f"Import abgeschlossen, {len(fehlerhafte)} mit Problemen", "warning")
            messagebox.showwarning(self.TITLE, "Nicht alles hat geklappt:\n\n" + "\n".join(fehlerhafte), parent=self.root)
        else:
            self.set_status(f"{len(zeilen)} Schnitt(e) importiert (BUG «Grundrisse/Schnitte»)", "ok")

    # ------------------------------------------------------------------ Hilfe und Schliessen
    def _zeige_hilfe(self) -> None:
        from ifc_schnitt_importer.shared.help_window import show_help

        try:
            show_help(self.root, f"Hilfe – {self.TITLE}")
        except Exception as exc:
            self.report_error(exc, "show_help", "Hilfe konnte nicht geöffnet werden")

    def on_close(self) -> None:
        save_value(_SETTINGS_FILE, _DIREKT_IMPORTIEREN_KEY, bool(self.direkt_importieren.get()))


def show_main_window(parent=None):
    return SchnittWorkflowWindow(parent).show()
