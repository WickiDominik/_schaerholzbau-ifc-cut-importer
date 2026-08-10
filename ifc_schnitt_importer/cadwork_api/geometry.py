"""Namespaced access to cadwork geometry APIs (geometry_controller)."""

import geometry_controller as _controller


def __getattr__(name):
    return getattr(_controller, name)
