"""Namespaced access to cadwork visualization APIs (visualization_controller)."""

import visualization_controller as _controller


def __getattr__(name):
    return getattr(_controller, name)
