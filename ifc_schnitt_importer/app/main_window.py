"""Kombiniertes Fenster: IFC Schnitt Generator + Importer in einem UI.

Ersetzt die frueher getrennten Fenster (siehe docs/konzept.md, Etappe 5
Teil 2) - ein Fenster fuer beide Schritte, mit Fortschrittsbalken statt
vollem Konsolen-Mitschnitt im UI. Ausfuehrliche Meldungen gehen weiterhin
per print() an die Cadwork-Konsole; das UI zeigt nur eine kurze
Zusammenfassung.

Threading-Modell (wichtig, siehe auch schnitt_generator/service.py):
- Cadwork-API-Aufrufe (ec.*/ac.*/vc.*) sind NUR vom Tkinter-Hauptthread
  aus sicher (Cadwork ist single-threaded).
- export_schnitt_definitionen() (Cadwork-API) laeuft synchron auf dem
  Hauptthread, bevor der externe Subprozess gestartet wird.
- Der generator_tool-Subprozess selbst (keine Cadwork-API) laeuft in
  einem Hintergrund-Thread, damit die Cadwork-UI waehrend der oft
  mehrminuetigen Verarbeitung ansprechbar bleibt; seine Ausgabe kommt
  ueber eine Queue zurueck und wird per `root.after`-Polling verarbeitet.
- import_schnitt() (Cadwork-API) laeuft wieder synchron auf dem
  Hauptthread, mit periodischen `update_idletasks()`-Aufrufen fuer die
  Fortschrittsanzeige (gleiches Muster wie in shb_toolcenter).
"""

from __future__ import annotations

import os
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from ifc_schnitt_importer.app.config import AppConfig, GeneratorToolConfig, SchnittDefinitionConfig
from ifc_schnitt_importer.shared.local_settings import load_value, save_value
from ifc_schnitt_importer.shared.logging import log_error_json
from ifc_schnitt_importer.shared.window_utils import get_or_create_root

_LAST_IFC_SETTINGS_KEY = "last_ifc_path"

# Anteil des Fortschrittsbalkens fuers Laden der IFC-Bauteile (der
# langsamste Teil bei grossen Projekten) vs. die anschliessende, deutlich
# schnellere Schnittberechnung je Definition.
_LADE_ANTEIL_PROZENT = 90


def show_main_window(parent=None):
    from ifc_schnitt_importer.features.schnitt_generator.service import (
        GeneratorToolNichtEingerichtetError,
        SchnittGeneratorService,
    )
    from ifc_schnitt_importer.features.schnitt_importer.service import SchnittImporterService
    from ifc_schnitt_importer.cadwork_api import project as uc

    root = get_or_create_root(parent)
    root.title(AppConfig.APP_NAME)
    root.geometry("760x640")
    root.minsize(680, 560)

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=AppConfig.APP_NAME, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

    _attr_range = SchnittDefinitionConfig.attribute_numbers()
    ttk.Label(
        frame,
        text=(
            f"Schnitt-Definitionen kommen aus den Benutzerattributen Nr. {_attr_range.start}-"
            f"{_attr_range.stop - 1} (ein Attribut je Schnitt, siehe Doku). "
            "Ausfuehrliche Meldungen erscheinen in der Cadwork-Konsole, hier nur eine Zusammenfassung."
        ),
        justify="left",
        wraplength=700,
    ).pack(anchor="w", pady=(4, 12))

    # ---- 1. Generieren ----
    gen_frame = ttk.LabelFrame(frame, text="1. Schnitte generieren", padding=10)
    gen_frame.pack(fill="x", pady=(0, 10))

    ifc_row = ttk.Frame(gen_frame)
    ifc_row.pack(fill="x")
    ttk.Label(ifc_row, text="IFC-Datei:").pack(side="left")
    ifc_path_var = tk.StringVar(value=load_value(GeneratorToolConfig.LAST_IFC_PATH_SETTINGS_FILE, _LAST_IFC_SETTINGS_KEY, ""))
    ttk.Entry(ifc_row, textvariable=ifc_path_var).pack(side="left", fill="x", expand=True, padx=(8, 8))

    def _browse_ifc():
        initial_dir = os.path.dirname(ifc_path_var.get()) if ifc_path_var.get() else None
        path = filedialog.askopenfilename(
            title="IFC-Datei waehlen",
            filetypes=[("IFC-Dateien", "*.ifc"), ("Alle Dateien", "*.*")],
            initialdir=initial_dir,
            parent=root,
        )
        if path:
            ifc_path_var.set(path)
            save_value(GeneratorToolConfig.LAST_IFC_PATH_SETTINGS_FILE, _LAST_IFC_SETTINGS_KEY, path)

    ttk.Button(ifc_row, text="Durchsuchen...", command=_browse_ifc).pack(side="left")

    gen_button_row = ttk.Frame(gen_frame)
    gen_button_row.pack(fill="x", pady=(8, 0))
    generate_button = ttk.Button(gen_button_row, text="Schnitte generieren")
    generate_button.pack(side="left")

    # ---- 2. Importieren ----
    import_frame = ttk.LabelFrame(frame, text="2. Schnitte importieren", padding=10)
    import_frame.pack(fill="both", expand=True, pady=(0, 10))

    list_row = ttk.Frame(import_frame)
    list_row.pack(fill="both", expand=True)
    listbox = tk.Listbox(list_row, selectmode=tk.EXTENDED, height=7)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(list_row, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.config(yscrollcommand=scrollbar.set)
    file_paths: list[str] = []

    import_button_row = ttk.Frame(import_frame)
    import_button_row.pack(fill="x", pady=(8, 0))
    refresh_button = ttk.Button(import_button_row, text="Liste aktualisieren")
    refresh_button.pack(side="left")
    import_button = ttk.Button(import_button_row, text="Ausgewaehlte importieren")
    import_button.pack(side="left", padx=(8, 0))

    # ---- Fortschritt + Zusammenfassung ----
    progress_bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
    progress_bar.pack(fill="x", pady=(4, 4))

    status_var = tk.StringVar(value="Bereit.")
    ttk.Label(frame, textvariable=status_var).pack(anchor="w")

    summary_text = tk.Text(frame, height=6, wrap="word")
    summary_text.pack(fill="x", pady=(8, 8))
    summary_text.config(state="disabled")

    def _set_status(text: str):
        status_var.set(text)

    def _set_summary(text: str):
        summary_text.config(state="normal")
        summary_text.delete("1.0", "end")
        summary_text.insert("1.0", text)
        summary_text.config(state="disabled")

    def _set_progress(value: float):
        progress_bar.config(value=max(0.0, min(100.0, value)))

    def _busy(is_busy: bool):
        state = "disabled" if is_busy else "normal"
        generate_button.config(state=state)
        import_button.config(state=state)
        refresh_button.config(state=state)

    def _refresh_list():
        listbox.delete(0, "end")
        file_paths.clear()
        try:
            service = SchnittImporterService()
            project_3d_file_path = uc.get_3d_file_path()
            found = service.list_available_exchange_files(project_3d_file_path)
            for path in found:
                file_paths.append(path)
                listbox.insert("end", os.path.basename(path))
            _set_status(f"{len(found)} Zwischendatei(en) gefunden." if found else "Keine Zwischendateien gefunden.")
        except Exception as e:
            _set_status("Fehler beim Suchen der Zwischendateien - siehe Konsole.")
            print(f"[main_window] Fehler beim Auflisten der Zwischendateien: {e}")
            log_error_json(e, module=__name__, action="list_exchange_files", function_name="_refresh_list")

    # ---- Schritt 1: Generieren ----

    _GENERATOR_LINE_PATTERNS = (
        re.compile(r"(\d+)\s+Kandidaten-Elemente"),
        re.compile(r"\.\.\.\s*(\d+)/(\d+)\s+geprueft"),
        re.compile(r"^\s*->\s*(.+?):\s*(\d+)\s+Flaechen,\s*(\d+)\s+Linien"),
    )

    def _run_generate():
        ifc_path = ifc_path_var.get().strip()
        if not ifc_path or not os.path.isfile(ifc_path):
            _set_status("Bitte zuerst eine gueltige IFC-Datei waehlen.")
            return

        save_value(GeneratorToolConfig.LAST_IFC_PATH_SETTINGS_FILE, _LAST_IFC_SETTINGS_KEY, ifc_path)
        _busy(True)
        _set_summary("")
        _set_progress(0)
        _set_status("Exportiere Schnitt-Definitionen ...")
        root.update_idletasks()

        def _step_export():
            # Cadwork-API - muss auf dem Hauptthread laufen.
            try:
                service = SchnittGeneratorService()
                service.ensure_attribute_label()
                definitionen_export, definitionen_datei = service.export_schnitt_definitionen()
            except Exception as e:
                _set_status("Fehler beim Export der Schnitt-Definitionen - siehe Konsole.")
                _set_summary(f"Fehler: {e}")
                print(f"[main_window] Fehler beim Export der Schnitt-Definitionen: {e}")
                log_error_json(e, module=__name__, action="export_schnitt_definitionen", function_name="_run_generate")
                _busy(False)
                return

            if not definitionen_export.definitionen:
                _set_status("Keine gueltigen Schnitt-Definitionen gefunden.")
                fehler_text = "\n".join(f"  - Element {f.element_id}: {f.fehler}" for f in definitionen_export.fehler)
                _set_summary("Keine Schnitt-Definitionen in den Benutzerattributen gefunden." + (f"\n\nFehler:\n{fehler_text}" if fehler_text else ""))
                _busy(False)
                return

            _set_status(f"{len(definitionen_export.definitionen)} Definition(en) gefunden. Starte generator_tool ...")
            root.update_idletasks()
            _step_subprocess(service, definitionen_export, definitionen_datei)

        def _step_subprocess(service, definitionen_export, definitionen_datei):
            # Der Subprozess selbst beruehrt keine Cadwork-API -> sicher
            # in einem Hintergrund-Thread, damit die UI ansprechbar bleibt.
            line_queue: "queue.Queue" = queue.Queue()
            result_holder: dict = {}

            def _worker():
                try:
                    result = service.generate_schnitte(
                        ifc_path,
                        definitionen_export,
                        definitionen_datei,
                        line_callback=lambda line: line_queue.put(("line", line)),
                    )
                    result_holder["result"] = result
                except Exception as e:
                    result_holder["error"] = e
                line_queue.put(("done", None))

            threading.Thread(target=_worker, daemon=True).start()

            def _handle_line(line: str):
                m = _GENERATOR_LINE_PATTERNS[1].search(line)
                if m:
                    current, total = int(m.group(1)), int(m.group(2))
                    if total:
                        _set_progress((current / total) * _LADE_ANTEIL_PROZENT)
                    _set_status(f"Lade IFC-Bauteile ... {current}/{total}")
                    return
                m = _GENERATOR_LINE_PATTERNS[0].search(line)
                if m:
                    _set_status(f"Lade {m.group(1)} Kandidaten-Elemente ...")
                    return
                m = _GENERATOR_LINE_PATTERNS[2].match(line)
                if m:
                    _set_progress(min(99, progress_bar["value"] + 2))
                    _set_status(f"Schnitt '{m.group(1)}' berechnet: {m.group(2)} Flaechen, {m.group(3)} Linien")
                    return

            def _poll_queue():
                try:
                    while True:
                        kind, payload = line_queue.get_nowait()
                        if kind == "line":
                            _handle_line(payload)
                        elif kind == "done":
                            _finish_generate(result_holder, definitionen_export)
                            return
                except queue.Empty:
                    pass
                root.after(100, _poll_queue)

            root.after(100, _poll_queue)

        def _finish_generate(result_holder, definitionen_export):
            _busy(False)

            if "error" in result_holder:
                e = result_holder["error"]
                _set_status("Generierung fehlgeschlagen.")
                if isinstance(e, GeneratorToolNichtEingerichtetError):
                    _set_summary(str(e))
                else:
                    _set_summary(f"Fehler: {e}")
                    print(f"[main_window] Fehler bei der Generierung: {e}")
                    log_error_json(e, module=__name__, action="generate_schnitte", function_name="_run_generate")
                return

            result = result_holder["result"]
            if result.subprocess_erfolgreich:
                _set_progress(100)
                _set_status("Generierung abgeschlossen.")
                zeilen = [f"{len(result.erzeugte_dateien)} von {len(definitionen_export.definitionen)} Schnitt(en) generiert:"]
                zeilen += [f"  - {os.path.basename(p)}" for p in result.erzeugte_dateien]
                _set_summary("\n".join(zeilen))
                _refresh_list()
            else:
                _set_status("Generierung fehlgeschlagen - Details siehe Cadwork-Konsole.")
                _set_summary("Generierung fehlgeschlagen. Details siehe Cadwork-Konsole.")

        root.after(50, _step_export)

    # ---- Schritt 2: Importieren ----

    def _run_import():
        selection = listbox.curselection()
        if not selection:
            _set_status("Bitte mindestens einen Schnitt auswaehlen.")
            return

        paths = [file_paths[i] for i in selection]
        _busy(True)
        _set_summary("")
        _set_progress(0)

        def _do_import():
            service = SchnittImporterService()
            zusammenfassung = []

            for index, path in enumerate(paths):
                basis_prozent = (index / len(paths)) * 100
                schritt_anteil = 100 / len(paths)

                def _progress(current, total, message, basis=basis_prozent, anteil=schritt_anteil):
                    anteil_fertig = (current / total) if total else 0
                    _set_progress(basis + anteil_fertig * anteil)
                    _set_status(message)
                    root.update_idletasks()

                try:
                    ergebnis = service.load(path)
                    result = service.import_schnitt(ergebnis, progress_callback=_progress)
                    zeile = f"{result.schnitt_name}: {result.erzeugte_flaechen} Flaechen"
                    if result.erzeugte_flaechen >= 2:
                        zeile += " (verbunden)" if result.flaechen_verbunden else " (NICHT verbunden, siehe Konsole)"
                    if result.erzeugte_linien:
                        zeile += f", {result.erzeugte_linien} Linien"
                    if result.ersetzte_alte_elemente:
                        zeile += f", {result.ersetzte_alte_elemente} alte ersetzt"
                    if result.fehler:
                        zeile += f", {len(result.fehler)} Fehler (siehe Konsole)"
                    zusammenfassung.append(zeile)
                except Exception as e:
                    zusammenfassung.append(f"{os.path.basename(path)}: Fehler - {e}")
                    print(f"[main_window] Fehler beim Import von {path}: {e}")
                    log_error_json(e, module=__name__, action="import_schnitt", function_name="_run_import")

            _set_progress(100)
            _set_status("Import abgeschlossen.")
            _set_summary("\n".join(zusammenfassung))
            _busy(False)

        root.after(50, _do_import)

    generate_button.config(command=_run_generate)
    refresh_button.config(command=_refresh_list)
    import_button.config(command=_run_import)

    ttk.Button(frame, text="Schliessen", command=root.destroy).pack(anchor="e", pady=(8, 0))

    _refresh_list()

    if isinstance(root, tk.Tk):
        root.mainloop()
