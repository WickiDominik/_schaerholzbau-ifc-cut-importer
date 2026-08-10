"""Namespaced access to cadwork's BIM/IFC APIs (bim_controller).

Key functions used by this plugin (verified against
https://docs.cadwork.com/projects/cwapi3dpython/en/latest/documentation/bim_controller/
on 2026-08-10, exact runtime behaviour still to be confirmed in Etappe 0):

- import_ifc_return_exchange_objects(file_path) -> list[ElementId]
    Native, lagerichtige IFC-Import als leichte "Exchange Objects" (kein
    Einfluss auf Stueckliste, kein direkter Materialbezug).
- convert_exchange_objects(exchange_objects) -> list[ElementId]
    Wandelt ausgewaehlte Exchange Objects in echte Cadwork-Elemente um,
    erst dann ist volle Geometrie (Facetten/Vertices) verfuegbar.
- get_all_storeys(building) / get_storey_height(building, storey)
- get_ifc2x3_element_type(element_id) / get_ifc_guid(element_id)
"""

import bim_controller as _controller


def __getattr__(name):
    return getattr(_controller, name)
