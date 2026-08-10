"""Holzbau IFC Schnitt Importer - main entry point with namespaced runtime.

Cadwork loads this file directly from the plugin folder and calls
`cadwork_menu()` to show the plugin's menu. All real logic lives in the
namespaced `ifc_schnitt_importer` package so this plugin never collides
with other Cadwork plugins that may load modules with generic names
(config, ui, utils, ...) in the same Python process.
"""

import os
import sys


script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from ifc_schnitt_importer.app.bootstrap import bootstrap_environment

bootstrap_environment()

# Clear only our namespaced modules so Cadwork picks up changes on disk
# without touching other plugins' generic module names.
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("ifc_schnitt_importer.") and mod_name != "ifc_schnitt_importer.app.bootstrap":
        del sys.modules[mod_name]

from ifc_schnitt_importer.app.main import cadwork_menu as _cadwork_menu


def cadwork_menu():
    """Display the plugin's main Cadwork menu."""
    return _cadwork_menu()


if __name__ == "__main__":
    cadwork_menu()
else:
    cadwork_menu()
