"""Centralized configuration for the IFC Schnitt Importer plugin."""

import os


class AppConfig:
    """Main application configuration."""

    APP_NAME = "Holzbau IFC Schnitt Importer"
    VERSION = "0.1.0"

    USER = os.environ.get("USERNAME", "").lower()
    ADMIN_USERS = ("domiw", "dominik.wicki", "boas.haenseler")

    # UI Configuration (aligned with schaerholzbau Toolcenter look & feel)
    BUTTON_COLOR = "navajowhite3"
    BUTTON_WIDTH = 24
    BUTTON_HOVER_COLOR = "red"


class PathConfig:
    """File and directory path configuration."""

    # Subdirectory (next to the active 3D file) where generated Schnitt
    # exchange files are written/read between the three stages:
    # Cadwork-Export -> externes Generator-Tool -> Cadwork-Import.
    EXCHANGE_SUBDIRECTORY = "IFC_Schnitte"

    # Bridging file: Cadwork-side export of Schnitt-Definitionen (Benutzer-
    # attribute), read by the external generator_tool together with the IFC.
    SCHNITT_DEFINITIONEN_FILENAME = "schnitt_definitionen.json"

    # Exchange file: one per Schnitt, named "<projekt>_<schnittname>.ifccut.json"
    EXCHANGE_FILE_SUFFIX = ".ifccut.json"

    @classmethod
    def get_exchange_directory(cls, project_3d_file_path: str) -> str:
        """Directory for generated Schnitt exchange files, next to the 3D file."""

        return os.path.join(os.path.dirname(project_3d_file_path), cls.EXCHANGE_SUBDIRECTORY)

    @classmethod
    def get_schnitt_definitionen_file_path(cls, project_3d_file_path: str) -> str:
        return os.path.join(cls.get_exchange_directory(project_3d_file_path), cls.SCHNITT_DEFINITIONEN_FILENAME)

    @classmethod
    def get_exchange_file_path(cls, project_3d_file_path: str, project_number: str, schnitt_name: str) -> str:
        directory = cls.get_exchange_directory(project_3d_file_path)
        filename = f"{project_number}_{schnitt_name}{cls.EXCHANGE_FILE_SUFFIX}"
        return os.path.join(directory, filename)


class SchnittDefinitionConfig:
    """Where/how the Schnitt-Definition is stored as a Cadwork Benutzerattribut.

    See shared/schnitt_definition.py for the text format itself. The
    attribute number is a plain Cadwork Benutzerattribut slot (1..N);
    picked distinct from slots already used by other schaerholzbau
    plugins (shb_toolcenter uses 4, 11-15) to avoid confusion, though
    slots are per-element so an actual collision is not possible.
    """

    ATTRIBUTE_NUMBER = 20
    ATTRIBUTE_LABEL = "IFC Schnitt-Definition"


class ReferenceGeometryConfig:
    """Configuration for the imported reference Flaechen/Linien.

    The imported geometry is explicitly kept apart from real Holzbau
    elements (own group/attribute, replaceable on re-import) but precise
    enough to be used as an underlay for Ausfuehrungsplanung.
    """

    GROUP_PREFIX = "IFC-Referenz"
    LINE_COLOR = 5  # Cadwork colour index, tuned during Etappe 4/5
    SURFACE_COLOR = 8
    COMMENT_TAG = "ifc_schnitt_import"


class UITextConfig:
    """UI text and menu configuration."""

    MENU_GENERATOR = "IFC Schnitt Generator"
    MENU_IMPORTER = "IFC Schnitt Importer"
    MENU_CLOSE = "Schliessen"

    MENU_OPTIONS = (
        MENU_GENERATOR,
        MENU_IMPORTER,
        "",
        MENU_CLOSE,
    )
