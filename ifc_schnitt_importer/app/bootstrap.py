"""Bootstrap helpers for the namespaced plugin runtime.

Mirrors the pattern used by the schaerholzbau Toolcenter
(`shb_toolcenter.app.bootstrap`) so both plugins behave consistently when
loaded in the same Cadwork Python process.
"""

from __future__ import annotations

import os
import sys


def project_root() -> str:
    """Return the `_schaerholzbau-ifc-schnitt-importer` project root."""

    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def ensure_project_root_on_path() -> str:
    """Ensure the project root is importable and return it."""

    root = project_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def bootstrap_environment() -> None:
    """Bootstrap vendored dependencies (if any) and prepare the runtime."""

    ensure_project_root_on_path()
    from ifc_schnitt_importer.shared.dependencies.bootstrap import bootstrap_plugin_environment

    bootstrap_plugin_environment()


def clear_namespaced_modules() -> None:
    """Clear only namespaced plugin modules from Python's import cache."""

    for mod_name in list(sys.modules):
        if mod_name.startswith("ifc_schnitt_importer.") and mod_name != __name__:
            del sys.modules[mod_name]
