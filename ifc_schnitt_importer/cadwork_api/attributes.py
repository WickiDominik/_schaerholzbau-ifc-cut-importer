"""Namespaced access to cadwork attribute APIs (attribute_controller)."""

import attribute_controller as _controller


def __getattr__(name):
    return getattr(_controller, name)
