"""Ebene x Bauteil-Mesh -> Schnittflaechen/-linien.

Fuer eine SchnittEbene (Ursprung + Normale, siehe shared/schnitt_format.py)
und eine Liste von IfcBauteilGeometrie (Dreiecksnetz, siehe ifc_reader.py)
wird je Bauteil der Schnitt mit der Ebene berechnet:

1. Jedes Dreieck, das die Ebene schneidet, liefert genau ein Liniensegment
   (klassischer Dreieck/Ebene-Schnitt ueber Vorzeichenwechsel der
   Eckpunkt-Abstaende zur Ebene).
2. Die Liniensegmente eines Bauteils werden zu Polylinien verkettet
   (Endpunkt-Matching mit Toleranz). Geschlossene Ketten (der Normalfall
   bei einem wasserdichten Solid wie Wand/Decke/Stuetze) ergeben je eine
   gefuellte Schnittflaeche UND ihre Konturlinien; offene Ketten (z.B. bei
   unsauberer Triangulierung) liefern nur Linien, keine Flaeche.

Reines Python, keine ifcopenshell-Abhaengigkeit - dadurch unit-testbar
ohne IFC-Datei (siehe generator_tool/tests/test_schnitt_berechnung.py).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, List, Tuple

from generator_tool.core.ifc_reader import IfcBauteilGeometrie
from ifc_schnitt_importer.shared.schnitt_format import SchnittEbene, SchnittFlaeche, SchnittLinie

Point3 = Tuple[float, float, float]

# Abstaende unterhalb dieser Schwelle (mm) gelten als "auf der Ebene".
EPSILON_MM = 1e-6

# Rundungspraezision (Nachkommastellen, mm) fuers Verketten von Segment-
# Endpunkten zu Polylinien. 2 Nachkommastellen = 1/100 mm Toleranz.
CHAIN_PRECISION = 2


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _lerp(a: Point3, b: Point3, t: float) -> Point3:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def normalize(v: Point3) -> Point3:
    length = math.sqrt(_dot(v, v))
    if length == 0:
        raise ValueError("Richtung ist ein Nullvektor, kann nicht normiert werden")
    return (v[0] / length, v[1] / length, v[2] / length)


# Toleranz (mm) fuer das Entfernen kollinearer Zwischenpunkte, die durch
# Trianguliersierungs-Diagonalen entstehen (z.B. eine Wandflaeche aus 2
# Dreiecken erzeugt an ihrer Schnittkante einen zusaetzlichen Punkt genau
# an der Diagonalen-Kreuzung). Rein kosmetisch/vereinfachend - aendert
# nicht die Form, nur die Punktanzahl.
COLLINEAR_TOLERANCE_MM = 1e-2


def _perpendicular_distance(point: Point3, a: Point3, b: Point3) -> float:
    ab = _sub(b, a)
    ab_len_sq = _dot(ab, ab)
    if ab_len_sq < 1e-12:
        diff = _sub(point, a)
        return math.sqrt(_dot(diff, diff))
    t = _dot(_sub(point, a), ab) / ab_len_sq
    closest = _lerp(a, b, t)
    diff = _sub(point, closest)
    return math.sqrt(_dot(diff, diff))


def _simplify_collinear(points: List[Point3], is_closed: bool, tolerance: float = COLLINEAR_TOLERANCE_MM) -> List[Point3]:
    """Entfernt Punkte, die (innerhalb `tolerance`) auf der Strecke ihrer
    beiden Nachbarn liegen. Bei geschlossenen Ketten ist `points[-1]`
    eine Wiederholung von `points[0]` (Ring) - diese Randbehandlung wird
    hier beruecksichtigt."""

    pts = list(points)
    ring_duplicate = is_closed and len(pts) > 1 and pts[0] == pts[-1]
    if ring_duplicate:
        pts = pts[:-1]

    min_points = 3 if is_closed else 2
    changed = True
    while changed and len(pts) > min_points:
        changed = False
        n = len(pts)
        new_pts = []
        for i in range(n):
            if not is_closed and (i == 0 or i == n - 1):
                new_pts.append(pts[i])
                continue
            prev_pt = pts[(i - 1) % n]
            next_pt = pts[(i + 1) % n]
            if _perpendicular_distance(pts[i], prev_pt, next_pt) < tolerance:
                changed = True
                continue
            new_pts.append(pts[i])
        pts = new_pts

    if ring_duplicate:
        pts = pts + [pts[0]]
    return pts


def _triangle_plane_intersection(
    triangle: Tuple[Point3, Point3, Point3], origin: Point3, normal: Point3
) -> Tuple[Point3, Point3] | None:
    """Segment (p_a, p_b), falls die Ebene das Dreieck-Innere schneidet, sonst None."""

    distances = [_dot(_sub(p, origin), normal) for p in triangle]
    # Eckpunkte exakt auf der Ebene minimal wegruecken, damit der
    # Vorzeichenwechsel-Algorithmus eindeutig bleibt (seltener Grenzfall).
    distances = [EPSILON_MM if abs(d) < EPSILON_MM else d for d in distances]

    signs = [d > 0 for d in distances]
    if all(signs) or not any(signs):
        return None  # Dreieck liegt komplett auf einer Seite

    points: List[Point3] = []
    for i in range(3):
        j = (i + 1) % 3
        if signs[i] != signs[j]:
            da, db = distances[i], distances[j]
            t = da / (da - db)
            points.append(_lerp(triangle[i], triangle[j], t))

    if len(points) != 2:
        # Entartet (z.B. Ebene beruehrt nur eine Ecke) - fuer v1 ignorieren.
        return None

    return (points[0], points[1])


def _quantize(p: Point3, precision: int = CHAIN_PRECISION) -> Tuple[float, float, float]:
    return (round(p[0], precision), round(p[1], precision), round(p[2], precision))


def _chain_segments(
    segments: Iterable[Tuple[Point3, Point3]], precision: int = CHAIN_PRECISION
) -> List[Tuple[List[Point3], bool]]:
    """Verkettet Segmente zu Polylinien.

    An normalen Punkten hat ein wasserdichtes Solid genau 2 anliegende
    Segmente - eindeutig. An Verzweigungspunkten (>2 anliegende Segmente,
    z.B. wenn eine Oeffnungskante numerisch nahe an einer Aussenkante zu
    liegen kommt und beide auf denselben gerundeten Punkt fallen) wird
    NICHT einfach der erste gefundene unbesuchte Anschluss genommen -
    das kann den Ring an der falschen Stelle schliessen und ein
    Dreieck/Fragment statt der vollen Kontur liefern. Stattdessen wird
    die Fortsetzung gewaehlt, die am "geradesten" zur bisherigen
    Laufrichtung passt (kleinster Winkel) - Standardtechnik beim
    Rekonstruieren von Konturen aus Ebenenschnitt-Segmenten.

    Rueckgabe: Liste von (Punkte, ist_geschlossen). Bei geschlossenen
    Ketten ist der letzte Punkt eine Wiederholung des ersten (Ring).
    """

    canonical: dict = {}
    adjacency: dict = defaultdict(list)  # key -> [(neighbor_key, edge_id), ...]
    edges: List[Tuple[tuple, tuple]] = []

    for pa, pb in segments:
        ka, kb = _quantize(pa, precision), _quantize(pb, precision)
        if ka == kb:
            continue  # Nulllaenge-Segment (numerisches Rauschen)
        canonical.setdefault(ka, pa)
        canonical.setdefault(kb, pb)
        edge_id = len(edges)
        edges.append((ka, kb))
        adjacency[ka].append((kb, edge_id))
        adjacency[kb].append((ka, edge_id))

    visited_edges: set = set()

    def _next_step(node_key, incoming_direction):
        """Waehlt unter den unbesuchten Anschluessen an `node_key` den mit
        der geradesten Fortsetzung zu `incoming_direction` (normiert,
        oder None fuer den allerersten Schritt einer Kette)."""

        candidates = [(nk, eid) for nk, eid in adjacency[node_key] if eid not in visited_edges]
        if not candidates:
            return None
        if len(candidates) == 1 or incoming_direction is None:
            return candidates[0]

        node_point = canonical[node_key]
        best = candidates[0]
        best_score = -2.0  # Kosinus liegt in [-1, 1]
        for neighbor_key, edge_id in candidates:
            direction = _sub(canonical[neighbor_key], node_point)
            direction_len = math.sqrt(_dot(direction, direction))
            if direction_len < 1e-9:
                continue
            cos_angle = _dot(incoming_direction, direction) / direction_len
            if cos_angle > best_score:
                best_score = cos_angle
                best = (neighbor_key, edge_id)
        return best

    def _direction(from_key, to_key):
        d = _sub(canonical[to_key], canonical[from_key])
        d_len = math.sqrt(_dot(d, d))
        return (d[0] / d_len, d[1] / d_len, d[2] / d_len) if d_len > 1e-9 else None

    chains: List[Tuple[List[Point3], bool]] = []

    for start_edge_id, (ka, kb) in enumerate(edges):
        if start_edge_id in visited_edges:
            continue
        visited_edges.add(start_edge_id)
        chain_keys = [ka, kb]

        # Vorwaerts von kb weiterlaufen, bis kein unbesuchter Anschluss
        # mehr da ist oder wir zum Startpunkt ka zurueckkommen (Ring zu).
        current = kb
        incoming = _direction(ka, kb)
        while True:
            nxt = _next_step(current, incoming)
            if nxt is None:
                break
            neighbor_key, edge_id = nxt
            visited_edges.add(edge_id)
            incoming = _direction(current, neighbor_key)
            chain_keys.append(neighbor_key)
            current = neighbor_key
            if current == ka:
                break

        is_closed = chain_keys[-1] == ka and len(chain_keys) > 2

        if not is_closed:
            # Falls nicht geschlossen: auch rueckwaerts von ka aus verlaengern.
            current = ka
            incoming = _direction(kb, ka)
            while True:
                nxt = _next_step(current, incoming)
                if nxt is None:
                    break
                neighbor_key, edge_id = nxt
                visited_edges.add(edge_id)
                incoming = _direction(current, neighbor_key)
                chain_keys.insert(0, neighbor_key)
                current = neighbor_key

        points = [canonical[k] for k in chain_keys]
        chains.append((points, is_closed))

    return chains


def berechne_schnitt(
    ebene: SchnittEbene,
    bauteile: Iterable[IfcBauteilGeometrie],
) -> Tuple[List[SchnittFlaeche], List[SchnittLinie]]:
    origin = tuple(ebene.origin)
    normal = normalize(tuple(ebene.normal))

    flaechen: List[SchnittFlaeche] = []
    linien: List[SchnittLinie] = []

    for bauteil in bauteile:
        segments = []
        for triangle in bauteil.dreiecke:
            segment = _triangle_plane_intersection(triangle, origin, normal)
            if segment is not None:
                segments.append(segment)

        if not segments:
            continue

        for raw_points, is_closed in _chain_segments(segments):
            points = _simplify_collinear(raw_points, is_closed)
            if len(points) < 2:
                continue

            for i in range(len(points) - 1):
                linien.append(
                    SchnittLinie(
                        start=list(points[i]),
                        end=list(points[i + 1]),
                        ifc_element_type=bauteil.ifc_type,
                        ifc_guid=bauteil.ifc_guid,
                    )
                )

            if is_closed:
                # Letzter Punkt ist die Wiederholung des ersten (Ring) -> weglassen.
                flaechen.append(
                    SchnittFlaeche(
                        vertices=[list(p) for p in points[:-1]],
                        ifc_element_type=bauteil.ifc_type,
                        ifc_guid=bauteil.ifc_guid,
                    )
                )

    return flaechen, linien
