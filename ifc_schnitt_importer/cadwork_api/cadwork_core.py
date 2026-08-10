"""Namespaced access to the base `cadwork` module (point_3d, vertex_list, ...).

Same pattern as shb_toolcenter.cadwork_api.cadwork_core - most element-
creation calls (create_polygon_panel, create_line_points, ...) require
these dedicated pybind11 types, not plain Python tuples/lists.
"""

import cadwork as module


def __getattr__(name):
    return getattr(module, name)
