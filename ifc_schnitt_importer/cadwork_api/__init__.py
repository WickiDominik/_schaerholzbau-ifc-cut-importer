"""Namespaced access to the Cadwork Python controller modules.

Direct `import element_controller` / `import bim_controller` etc. calls are
kept out of feature code; everything goes through this package so the
plugin has one place to adapt if Cadwork renames/changes a controller.
"""
