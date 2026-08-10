"""Namespaced entry points for the IFC Schnitt Importer plugin."""

from __future__ import annotations

from ifc_schnitt_importer.app.bootstrap import bootstrap_environment


def cadwork_menu():
    """Display the plugin's menu."""

    bootstrap_environment()
    from ifc_schnitt_importer.app.menu_controller import MenuController

    return MenuController().show_cadwork_menu()
