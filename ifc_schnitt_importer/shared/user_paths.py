"""Pro-Benutzer-Ablageort fuer lokale Einstellungen und Logs.

Das Plugin kann zentral (z.B. auf einem Netzlaufwerk oder unter
ProgramData) liegen und ist dann fuer normale Benutzer oft nicht
beschreibbar - ausserdem wuerden sich sonst alle Benutzer z.B. den
"zuletzt gewaehlten IFC-Pfad" teilen. Deshalb liegen Einstellungen und
Logs unter %APPDATA% (Windows) bzw. ~/.config, mit Rueckfall auf den
Plugin-Ordner, falls dort nichts angelegt werden kann.
"""

from __future__ import annotations

import os

_APP_FOLDER = os.path.join("schaerholzbau", "ifc_schnitt_importer")


def _plugin_package_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _user_base_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, _APP_FOLDER)


def user_data_dir(subfolder: str) -> str:
    """Beschreibbarer Ordner `<APPDATA>/schaerholzbau/ifc_schnitt_importer/<subfolder>`.

    Faellt auf `ifc_schnitt_importer/<subfolder>` im Plugin-Ordner zurueck,
    wenn der Benutzer-Ordner nicht angelegt werden kann.
    """

    for candidate in (
        os.path.join(_user_base_dir(), subfolder),
        os.path.join(_plugin_package_dir(), subfolder),
    ):
        try:
            os.makedirs(candidate, exist_ok=True)
            return candidate
        except OSError:
            continue
    # Letzter Ausweg: Pfad trotzdem zurueckgeben, Schreibfehler werden von
    # den Aufrufern abgefangen.
    return os.path.join(_plugin_package_dir(), subfolder)
