"""Simple-menu controller for the IFC Schnitt Importer plugin.

Uses Cadwork's native `menu_controller.display_simple_menu(...)` the same
way the schaerholzbau Toolcenter does, so the plugin behaves consistently
in both the Cadwork Shell and the live Cadwork API menu.
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

            if selection == self.ui_text.MENU_GENERATOR:
                self._handle_generator()
                break
            elif selection == self.ui_text.MENU_IMPORTER:
                self._handle_importer()
                break
            elif selection == self.ui_text.MENU_CLOSE or selection is None:
                self._handle_exit()
                break

    def _handle_generator(self):
        try:
            from ifc_schnitt_importer.features.schnitt_generator.window import show_schnitt_generator_window

            show_schnitt_generator_window(parent=None)
        except Exception as e:
            print(f"Error opening Schnitt Generator: {e}")
            import traceback

            traceback.print_exc()
            log_error_json(e, module=__name__, action="open_schnitt_generator", function_name="MenuController._handle_generator")

    def _handle_importer(self):
        try:
            from ifc_schnitt_importer.features.schnitt_importer.window import show_schnitt_importer_window

            show_schnitt_importer_window(parent=None)
        except Exception as e:
            print(f"Error opening Schnitt Importer: {e}")
            import traceback

            traceback.print_exc()
            log_error_json(e, module=__name__, action="open_schnitt_importer", function_name="MenuController._handle_importer")

    def _handle_exit(self):
        print("Holzbau IFC Schnitt Importer wird beendet...")
