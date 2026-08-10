"""Namespaced access to cadwork project/utility APIs (utility_controller)."""

import utility_controller as _controller


def __getattr__(name):
    return getattr(_controller, name)
