"""Dependency bootstrap for the IFC Schnitt Importer plugin.

Unlike the schaerholzbau Toolcenter, this plugin currently needs NO third
party packages: the whole IFC handling goes through Cadwork's own
`bim_controller` (see cadwork_api/bim.py), and the UI is plain Tkinter
(stdlib). This file exists mainly so the structure matches the Toolcenter
conventions and so we have a single place to wire in a
`site-packages-pyX.Y` folder later if a feature ever needs one (e.g. an
optional pure-Python fallback parser).

Supported Cadwork-embedded Python versions, mirrored from
shb_toolcenter for reference: 3.12 (SP2025 and older), 3.14 (SP2026).
"""

from __future__ import annotations

import sys

SUPPORTED_PYTHON_VERSIONS = ((3, 12), (3, 14))


def bootstrap_plugin_environment() -> None:
    """No-op today; kept as the extension point for future dependencies."""

    version = sys.version_info[:2]
    if version not in SUPPORTED_PYTHON_VERSIONS:
        print(
            f"[ifc_schnitt_importer] Warnung: ungetestete Python-Version {version}, "
            f"unterstuetzt sind {SUPPORTED_PYTHON_VERSIONS}"
        )
