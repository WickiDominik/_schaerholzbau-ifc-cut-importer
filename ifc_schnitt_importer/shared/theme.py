"""Aussehen wie im schaerholzbau Toolcenter (Kopie von shb_toolcenter.shared.theme).

``ToolWindow`` ruft :func:`apply_theme` für jedes Fenster auf und setzt Kopfband, Grösse und Position.
Farben, Schriften und Knopfarten stehen nur hier, damit alle Fenster gleich aussehen.

Knopfarten (ttk-Stile): ``TButton`` (Standard), ``Primary.TButton`` (Hauptaktion eines Fensters),
``Danger.TButton`` (Schliessen) und ``Success.TButton``.
"""

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from ifc_schnitt_importer.shared.window_geometry import get_cadwork_dpi, get_work_area

# Farben (wie im Helpcenter)
BG = "#f4f1ec"            # Fensterhintergrund (warmes Hellgrau)
SURFACE = "#ffffff"       # Tabellen, Eingabefelder
BORDER = "#d8d1c6"
HEADER_BG = "#5a4632"     # dunkles Holz
HEADER_FG = "#ffffff"
HEADER_SUB_FG = "#e3d6c4"
HEADER_BUTTON_BG = "#76604a"          # Knopf im Kopfband (Hilfe)
HEADER_BUTTON_ACTIVE_BG = "#8d755c"
TEXT = "#2b2622"
MUTED = "#6e665d"         # Hinweise
ACCENT = "#5a4632"        # Rahmentitel
LINK = "#1f5fa8"
SUCCESS = "#2e7d32"
WARNING = "#b26a00"
ERROR = "#b3261e"
ROW_WARNING_BG = "#fdf0d5"   # Tabellenzeilen im Log
ROW_ERROR_BG = "#f9dcd9"
ROW_CRITICAL_BG = "#f2bdb8"

BUTTON_VARIANTS = {
    # Art: (Hintergrund, Schrift)
    "primary": ("#8b6b4a", "#ffffff"),
    "secondary": ("#e6ded2", TEXT),
    "danger": ("#b94a48", "#ffffff"),
    "success": ("#3f7f4f", "#ffffff"),
}

# Schriften (Segoe UI ist die Windows-Systemschrift; anderswo ersetzt Tk sie automatisch)
FAMILY = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
FONT = (FAMILY, 9)
FONT_BOLD = (FAMILY, 9, "bold")
FONT_ITALIC = (FAMILY, 9, "italic")
FONT_SMALL = (FAMILY, 8)
FONT_HINT = (FAMILY, 8, "italic")
FONT_LARGE = (FAMILY, 10)
FONT_SECTION = (FAMILY, 10, "bold")
FONT_TITLE = (FAMILY, 13, "bold")
FONT_BUTTON = (FAMILY, 9, "bold")
FONT_FIXED = ("Consolas", 9) if sys.platform == "win32" else ("DejaVu Sans Mono", 9)

PAD = 12   # Aussenabstand aller Fenster


def darker(widget, color: str, factor: float = 0.82) -> str:
    """Dunklere Variante von *color* (für Hover und gedrückte Knöpfe)."""
    try:
        red, green, blue = (int(c / 257 * factor) for c in widget.winfo_rgb(color))
        return f"#{red:02x}{green:02x}{blue:02x}"
    except (tk.TclError, ValueError):
        return color


def _sync_dpi(root) -> None:
    """Schriftskalierung an die DPI des Monitors anpassen, auf dem Cadwork läuft.

    Tk liest die System-DPI nur beim Start; auf einem zweiten Monitor mit anderer Windows-Skalierung
    (z.B. 150 %) wären die Schriften sonst zu klein oder zu gross.
    """
    dpi = get_cadwork_dpi()
    if not dpi:
        return
    try:
        if abs(root.winfo_fpixels("1i") - dpi) > 2:
            root.tk.call("tk", "scaling", dpi / 72.0)
    except tk.TclError:
        pass


def scale(widget) -> float:
    """Faktor zwischen der aktuellen Anzeige und 100 % Windows-Skalierung (96 DPI)."""
    try:
        return max(1.0, widget.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        return 1.0


def px(widget, value: float) -> int:
    """Pixelmass für 100 % auf die aktuelle Anzeige umrechnen."""
    return int(round(value * scale(widget)))


def apply_theme(root) -> None:
    """Farben, Schriften, Knopfarten und DPI-Skalierung für ein neues Fenster (Tk oder Toplevel)."""
    _sync_dpi(root)
    root.configure(bg=BG)
    # Klassische Tk-Widgets (Text, Listbox, Canvas …) über die Optionsdatenbank
    root.option_add("*Font", FONT)
    root.option_add("*Background", BG)
    root.option_add("*Foreground", TEXT)
    root.option_add("*Entry.Background", SURFACE)
    root.option_add("*Text.Background", SURFACE)
    root.option_add("*Listbox.Background", SURFACE)
    root.option_add("*Text.relief", "solid")
    root.option_add("*Listbox.relief", "solid")
    root.option_add("*Text.borderWidth", 1)
    root.option_add("*Listbox.borderWidth", 1)
    root.option_add("*selectBackground", BUTTON_VARIANTS["primary"][0])
    root.option_add("*selectForeground", "#ffffff")
    # Auswahllisten der Comboboxen
    root.option_add("*TCombobox*Listbox.background", SURFACE)
    root.option_add("*TCombobox*Listbox.font", FONT)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")   # das einzige eingebaute Theme, das Farben überall übernimmt
    except tk.TclError:
        pass
    style.configure(".", background=BG, foreground=TEXT, font=FONT, bordercolor=BORDER,
                    troughcolor=BORDER, focuscolor=BUTTON_VARIANTS["primary"][0])
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("TLabelframe", background=BG, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT, font=FONT_SECTION)
    style.configure("TCheckbutton", background=BG)
    style.configure("TRadiobutton", background=BG)
    style.map("TCheckbutton", background=[("active", BG)])
    style.map("TRadiobutton", background=[("active", BG)])
    style.configure("TNotebook", background=BG, bordercolor=BORDER)
    style.configure("TNotebook.Tab", padding=(12, 4), font=FONT_BOLD)
    style.map("TNotebook.Tab", background=[("selected", SURFACE)])
    style.configure("TSeparator", background=BORDER)
    row_height = tkfont.Font(root=root, font=FONT).metrics("linespace") + px(root, 6)
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, rowheight=row_height,
                    bordercolor=BORDER)
    style.configure("Treeview.Heading", font=FONT_BOLD, background=BUTTON_VARIANTS["secondary"][0])
    style.map("Treeview", background=[("selected", BUTTON_VARIANTS["primary"][0])],
              foreground=[("selected", "#ffffff")])
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground=SURFACE, bordercolor=BORDER)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE)])
    style.configure("Horizontal.TProgressbar", background=BUTTON_VARIANTS["primary"][0],
                    troughcolor=SURFACE, bordercolor=BORDER)

    for variant, (background, foreground) in BUTTON_VARIANTS.items():
        name = "TButton" if variant == "secondary" else f"{variant.title()}.TButton"
        # width -6: mindestens 6 Zeichen breit, sonst so breit wie der Text (clam: mindestens 11)
        style.configure(name, background=background, foreground=foreground, font=FONT_BUTTON,
                        padding=(10, 4), borderwidth=0, focuscolor=background, width=-6)
        style.map(name, background=[("disabled", BORDER), ("active", darker(root, background))],
                  foreground=[("disabled", MUTED)])


def create_header(parent, title: str, subtitle: str = "") -> tk.Frame:
    """Dunkles Kopfband mit Titel und Untertitel (der Aufrufer platziert es).

    Die Labels stehen in ``header.title_label`` und ``header.subtitle_label``.
    """
    header = tk.Frame(parent, bg=HEADER_BG)
    header.title_label = tk.Label(header, text=title, bg=HEADER_BG, fg=HEADER_FG, font=FONT_TITLE,
                                  anchor="w")
    header.title_label.pack(fill="x", padx=PAD, pady=(10, 0 if subtitle else 10))
    header.subtitle_label = tk.Label(header, text=subtitle, bg=HEADER_BG, fg=HEADER_SUB_FG, font=FONT_SMALL,
                                     anchor="w", justify="left")
    if subtitle:
        header.subtitle_label.pack(fill="x", padx=PAD, pady=(0, 10))
    return header


def add_header_button(header: tk.Frame, text: str, command) -> tk.Button:
    """Knopf rechts im Kopfband (z.B. "Hilfe"); liegt über dem Titel, damit dessen Layout bleibt."""
    button = tk.Button(header, text=text, command=command, bg=HEADER_BUTTON_BG, fg=HEADER_FG,
                       activebackground=HEADER_BUTTON_ACTIVE_BG, activeforeground=HEADER_FG, font=FONT_BUTTON,
                       relief="flat", bd=0, padx=10, pady=3, cursor="hand2", highlightthickness=0)
    button.place(relx=1.0, rely=0.5, x=-PAD, anchor="e")
    return button


def set_header(header: tk.Frame, title: str, subtitle: str = "") -> None:
    """Titel und Untertitel eines Kopfbands ändern."""
    header.title_label.configure(text=title)
    header.subtitle_label.configure(text=subtitle)
    if subtitle and not header.subtitle_label.winfo_manager():
        header.title_label.pack_configure(pady=(10, 0))
        header.subtitle_label.pack(fill="x", padx=PAD, pady=(0, 10))
    elif not subtitle and header.subtitle_label.winfo_manager():
        header.subtitle_label.pack_forget()
        header.title_label.pack_configure(pady=10)


def parse_size(size: str):
    """``"BreitexHöhe"`` → (Breite, Höhe)."""
    width, height = size.lower().split("x")
    return int(width), int(height)


def place_window(root, width: int, height: int, offset=(0, 0), min_size=(320, 240)):
    """Fenster so gross und so platzieren, dass es ganz auf den Arbeitsbereich des Monitors passt.

    *width*/*height* sind die gewünschte Grösse bei 100 % Windows-Skalierung; sie werden auf die Anzeige
    umgerechnet und verkleinert, wenn der Bildschirm kleiner ist. Das Fenster erscheint bei *offset*
    (neben Cadwork), wird aber zurückgeschoben, wenn es über den Rand ragen würde. Liefert (Breite, Höhe).
    """
    factor = scale(root)
    left, top, right, bottom = get_work_area(root, *offset)
    margin = px(root, 20)
    title_bar = px(root, 40)   # Fensterrahmen gehört nicht zur Tk-Geometrie
    max_width = max(200, right - left - 2 * margin)
    max_height = max(200, bottom - top - 2 * margin - title_bar)
    width = min(int(width * factor), max_width)
    height = min(int(height * factor), max_height)

    x, y = offset
    x = min(max(x, left + margin), right - margin - width)
    y = min(max(y, top + margin), bottom - margin - title_bar - height)
    root.geometry(f"{width}x{height}+{int(x)}+{int(y)}")
    root.minsize(int(min(min_size[0] * factor, width)), int(min(min_size[1] * factor, height)))
    return width, height
