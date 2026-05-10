from typing import List

from fastapi import Request

from fairlead_core.units import search_unit_iri_by_name, fetch_unit_object_from_qudt_unit_iri, \
    fetch_unit_iri_by_fragments
from simpler_api.apis.units_api_base import BaseUnitsApi
from simpler_api.impl.mapping import make_unit
from simpler_model import Unit

#
# class UnitsApi(BaseUnitsApi):
#     def search_units(
#         self,
#         request: Request,
#         search_string: list[str],
#         limit: int,
#     ) -> List[Unit]:
#         """Fetch units based on a query string"""
#
#         iris = fetch_unit_iri_by_fragments(tuple(search_string))[:limit]
#         # iris = search_unit_iri_by_name(search_string, limit)
#         linkml_units = fetch_unit_object_from_qudt_unit_iri(tuple(iris))
#         units = [make_unit(x) for x in linkml_units]
#         return units
