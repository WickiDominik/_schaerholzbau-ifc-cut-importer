"""Tiny per-machine JSON settings helper (e.g. "last used IFC path").

Not project data (that belongs next to the 3D file, see PathConfig) -
this is purely local UI convenience state, stored under
ifc_schnitt_importer/settings/.
"""

from __future__ import annotations

import json
import os

from ifc_schnitt_importer.app.bootstrap import project_root


def _settings_dir() -> str:
    path = os.path.join(project_root(), "ifc_schnitt_importer", "settings")
    os.makedirs(path, exist_ok=True)
    return path


def load_value(filename: str, key: str, default=None):
    path = os.path.join(_settings_dir(), filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(key, default)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_value(filename: str, key: str, value) -> None:
    path = os.path.join(_settings_dir(), filename)
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    data[key] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
