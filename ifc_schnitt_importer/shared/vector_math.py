"""Minimal 3D vector helpers shared by Cadwork-plugin code.

Deliberately tiny and dependency-free (no numpy) - the plugin runs
inside Cadwork's embedded Python where we don't control the available
site-packages. For the heavier geometry math see generator_tool/core/
schnitt_berechnung.py (separate runtime, see docs/konzept.md).
"""

from __future__ import annotations

import math
from typing import Tuple

Point3 = Tuple[float, float, float]


def subtract(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def length(v: Point3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def normalize(v: Point3) -> Point3:
    l = length(v)
    if l == 0:
        raise ValueError("Nullvektor kann nicht normiert werden")
    return (v[0] / l, v[1] / l, v[2] / l)
