"""Namespaced access to cadwork element APIs (element_controller)."""

import element_controller as _controller


def __getattr__(name):
    return getattr(_controller, name)
