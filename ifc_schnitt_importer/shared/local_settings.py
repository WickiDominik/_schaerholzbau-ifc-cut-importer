"""Tiny per-user JSON settings helper (e.g. "last used IFC path").

Not project data (that belongs next to the 3D file, see PathConfig) -
this is purely local UI convenience state, stored per Windows user under
%APPDATA% (see shared/user_paths.py).

Lesen und Schreiben sind best-effort: ein nicht beschreibbarer Ordner
darf nie den eigentlichen Arbeitsablauf (Generieren/Importieren)
abbrechen.
"""

from __future__ import annotations

import json
import os

from ifc_schnitt_importer.shared.user_paths import user_data_dir


def _settings_dir() -> str:
    return user_data_dir("settings")


def load_value(filename: str, key: str, default=None):
    path = os.path.join(_settings_dir(), filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(key, default)
    except (OSError, ValueError, AttributeError):
        return default


def save_value(filename: str, key: str, value) -> None:
    path = os.path.join(_settings_dir(), filename)
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        pass
    data[key] = value
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[ifc_schnitt_importer] Einstellung '{key}' konnte nicht gespeichert werden: {e}")
