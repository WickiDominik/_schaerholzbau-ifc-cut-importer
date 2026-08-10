"""UI window for the IFC Schnitt Generator (Cadwork-Seite).

STATUS: Etappe 2 + 5 (implementiert). Deckt beide Cadwork-seitigen
Schritte in einem Fenster ab: Schnitt-Definitionen aus dem Modell
exportieren UND das externe generator_tool direkt anstossen (IFC-Datei
waehlen -> Schnitte generieren), ohne dass der Anwender selbst ein
Terminal bedienen muss. Siehe docs/konzept.md.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk

from ifc_schnitt_importer.app.config import AppConfig, GeneratorToolConfig, SchnittDefinitionConfig
from ifc_schnitt_importer.shared.local_settings import load_value, save_value
from ifc_schnitt_importer.shared.logging import log_error_json
from ifc_schnitt_importer.shared.window_utils import get_or_create_root

_LAST_IFC_SETTINGS_KEY = "last_ifc_path"


def show_schnitt_generator_window(parent=None):
    root = get_or_create_root(parent)
    root.title(f"{AppConfig.APP_NAME} - Schnitt Generator")
    root.geometry("700x560")

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="IFC Schnitt Generator",
        font=("TkDefaultFont", 12, "bold"),
    ).pack(anchor="w")

    _attribut_bereich = SchnittDefinitionConfig.attribute_numbers()
    ttk.Label(
        frame,
        text=(
            f"Schnitt-Definitionen kommen aus den Benutzerattributen Nr. {_attribut_bereich.start}-"
            f"{_attribut_bereich.stop - 1} (\"{SchnittDefinitionConfig.ATTRIBUTE_LABEL} 1\", \"... 2\", ...), z.B.\n"
            "  Name=Schnitt A-A;Typ=vertikal;Ursprung=1234.5,6789.0,0;Richtung=0,1,0\n\n"
            f"Mehrere Schnitte auf einem Element: je EIN Attribut pro Schnitt "
            f"(Attribut {_attribut_bereich.start} = 1. Schnitt, {_attribut_bereich.start + 1} = 2. Schnitt, ...) "
            "- Cadwork-Attribute sind auf ca. 128 Zeichen begrenzt, daher nicht mehrzeilig in EINEM Attribut."
        ),
        justify="left",
        wraplength=660,
    ).pack(anchor="w", pady=(8, 12))

    # --- IFC-Datei-Auswahl ---
    ifc_row = ttk.Frame(frame)
    ifc_row.pack(fill="x", pady=(0, 4))
    ttk.Label(ifc_row, text="IFC-Datei:").pack(side="left")

    ifc_path_var = tk.StringVar(value=load_value(GeneratorToolConfig.LAST_IFC_PATH_SETTINGS_FILE, _LAST_IFC_SETTINGS_KEY, ""))
    ifc_entry = ttk.Entry(ifc_row, textvariable=ifc_path_var)
    ifc_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))

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

    # --- Ergebnisanzeige ---
    result_text = tk.Text(frame, height=18, wrap="word")
    result_text.pack(fill="both", expand=True, pady=(12, 10))
    result_text.insert("1.0", "Noch nicht ausgefuehrt.")
    result_text.config(state="disabled")

    status_var = tk.StringVar(value="")
    ttk.Label(frame, textvariable=status_var).pack(anchor="w")

    def _set_result_text(text: str):
        result_text.config(state="normal")
        result_text.delete("1.0", "end")
        result_text.insert("1.0", text)
        result_text.config(state="disabled")

    def _run_export_only():
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
            status_var.set(f"Definitionen exportiert: {len(result.definitionen)} gefunden, {len(result.fehler)} Fehler")
        except Exception as e:
            _set_result_text(f"Fehler beim Export: {e}")
            status_var.set("Fehler - siehe Log")
            log_error_json(e, module=__name__, action="export_schnitt_definitionen", function_name="_run_export_only")
            import traceback

            traceback.print_exc()

    def _run_generate():
        ifc_path = ifc_path_var.get().strip()
        if not ifc_path:
            status_var.set("Bitte zuerst eine IFC-Datei waehlen.")
            return
        if not os.path.isfile(ifc_path):
            status_var.set(f"IFC-Datei nicht gefunden: {ifc_path}")
            return

        save_value(GeneratorToolConfig.LAST_IFC_PATH_SETTINGS_FILE, _LAST_IFC_SETTINGS_KEY, ifc_path)

        generate_button.config(state="disabled")
        status_var.set("Generiere Schnitte... (kann bei grossen IFC-Dateien einige Zeit dauern)")
        _set_result_text("Generiere Schnitte...")
        root.update_idletasks()

        def _do_generate():
            try:
                from ifc_schnitt_importer.features.schnitt_generator.service import (
                    GeneratorToolNichtEingerichtetError,
                    SchnittGeneratorService,
                )

                service = SchnittGeneratorService()
                ergebnis = service.generate_schnitte(ifc_path)

                lines = [
                    f"{len(ergebnis.definitionen_export.definitionen)} Schnitt-Definition(en) gefunden "
                    f"({len(ergebnis.definitionen_export.fehler)} Fehler beim Einlesen)",
                    f"IFC: {ergebnis.ifc_datei}",
                    "",
                ]
                if ergebnis.subprocess_erfolgreich:
                    lines.append(f"{len(ergebnis.erzeugte_dateien)} Schnitt(e) erfolgreich generiert:")
                    for path in ergebnis.erzeugte_dateien:
                        lines.append(f"  - {os.path.basename(path)}")
                else:
                    lines.append("Generierung fehlgeschlagen.")
                lines.append("\n--- Ausgabe des Generator-Tools ---")
                lines.append(ergebnis.subprocess_ausgabe or "(keine Ausgabe)")

                _set_result_text("\n".join(lines))
                if ergebnis.subprocess_erfolgreich:
                    status_var.set(f"Fertig: {len(ergebnis.erzeugte_dateien)} Schnitt(e) generiert.")
                else:
                    status_var.set("Generierung fehlgeschlagen - siehe Ausgabe unten.")
            except GeneratorToolNichtEingerichtetError as e:
                _set_result_text(str(e))
                status_var.set("Generator-Tool nicht eingerichtet - siehe Hinweis unten.")
            except Exception as e:
                _set_result_text(f"Fehler: {e}")
                status_var.set("Fehler - siehe Log")
                log_error_json(e, module=__name__, action="generate_schnitte", function_name="_run_generate")
                import traceback

                traceback.print_exc()
            finally:
                generate_button.config(state="normal")

        # Kurz verzoegern, damit die UI den "Generiere..."-Status noch
        # anzeigt, bevor der (blockierende) Subprozess-Aufruf laeuft -
        # gleiches Muster wie in shb_toolcenter fuer lange Operationen.
        root.after(100, _do_generate)

    button_row = ttk.Frame(frame)
    button_row.pack(fill="x")
    ttk.Button(button_row, text="Nur Schnitt-Definitionen exportieren", command=_run_export_only).pack(side="left")
    generate_button = ttk.Button(button_row, text="Schnitte generieren", command=_run_generate)
    generate_button.pack(side="left", padx=(8, 0))
    ttk.Button(button_row, text="Schliessen", command=root.destroy).pack(side="right")

    if isinstance(root, tk.Tk):
        root.mainloop()
