"""Simple-menu controller for the IFC Schnitt Importer plugin.

Uses Cadwork's native `menu_controller.display_simple_menu(...)` the same
way the schaerholzbau Toolcenter does, so the plugin behaves consistently
in both the Cadwork Shell and the live Cadwork API menu.

Generator und Importer laufen in EINEM Fenster (app/main_window.py) -
siehe docs/konzept.md, Etappe 5 Teil 2. Daher nur noch ein Menuepunkt.
"""

from __future__ import annotations

from ifc_schnitt_importer.app.config import UITextConfig
from ifc_schnitt_importer.shared.logging import log_error_json


class MenuController:
    """Controls the plugin's simple-menu interface."""

    def __init__(self):
        self.ui_text = UITextConfig()

    def show_cadwork_menu(self):
        import menu_controller as mec

        while True:
            selection = mec.display_simple_menu(self.ui_text.MENU_OPTIONS)
            print(f"[IFC Schnitt Importer] Menu selection: {selection}")

            if selection == self.ui_text.MENU_MAIN:
                self._handle_main_window()
                break
            elif selection == self.ui_text.MENU_CLOSE or selection is None:
                self._handle_exit()
                break

    def _handle_main_window(self):
        try:
            from ifc_schnitt_importer.app.main_window import show_main_window

            show_main_window(parent=None)
        except Exception as e:
            print(f"Error opening IFC Schnitt Importer window: {e}")
            import traceback

            traceback.print_exc()
            log_error_json(e, module=__name__, action="open_main_window", function_name="MenuController._handle_main_window")

    def _handle_exit(self):
        print("Holzbau IFC Schnitt Importer wird beendet...")
