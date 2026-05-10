from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND

from fairlead_core.units import search_unit_iri_by_name, fetch_unit_object_from_qudt_unit_iri, \
    search_unit_iri_by_search_strings, match_units_to_search_strings, get_all_units
from simpler_api.apis.semantics_api_base import BaseSemanticsApi
from simpler_api.impl.mapping import make_unit
from simpler_model import Quantity, Unit


class SemanticsApi(BaseSemanticsApi):
    def get_jsonld_context(
            self,
            request: Request,
    ) -> str:
        return RedirectResponse(url="/semantics/static/context.jsonld", status_code=HTTP_302_FOUND)

    def get_ontology(
            self,
            request: Request,
    ) -> str:
        requested_data_type = request.headers['accept']
        if requested_data_type == 'text/turtle':
            return RedirectResponse(url="/semantics/static/ero.ttl", status_code=HTTP_302_FOUND)
        else:
            return RedirectResponse(url="/semantics/ontology/docs/index.html", status_code=HTTP_302_FOUND)

    def get_concept(
            self,
            request: Request,
            concept: str,
    ) -> str:
        requested_data_type = request.headers['accept']
        if requested_data_type == 'text/turtle':
            return RedirectResponse(url="/semantics/static/ero.ttl", status_code=HTTP_302_FOUND)
        else:
            return RedirectResponse(url=f"/semantics/ontology/docs/{concept}", status_code=HTTP_302_FOUND)

    def search_quantity_kinds(
        self,
        request: Request,
        search_string: list[str],
        limit: int,
    ) -> list[Quantity]:
        """Fetch quantity kinds based on a query string"""
        ...


    def search_units(
        self,
        request: Request,
        search_string: list[str],
        limit: int,
    ) -> list[Unit]:
        """Fetch units based on a query string"""
        # iris = fetch_unit_iri_by_fragments(tuple(search_string))[:limit]
        iris = search_unit_iri_by_search_strings(tuple(search_string))[:limit]
        if not iris:
            return []
        linkml_units = fetch_unit_object_from_qudt_unit_iri(tuple(iris))
        units = [make_unit(x) for x in linkml_units]
        return units

    def match_units(
        self,
        request: Request,
        unit_iris: list[str],
        unit_texts: list[str],
    ) -> dict[str, str]:
        """Find the best unit of a given set to a set of texts"""

        # Fetch empty calls of this
        if '' in unit_iris:
            unit_iris.remove('')
        if '' in unit_texts:
            unit_texts.remove('')

        if len(unit_texts) == 0 or len(unit_iris) == 0:
            return {}

        return {
            key: linkml_unit.descriptive_name if linkml_unit is not None else ''
            for key, linkml_unit in match_units_to_search_strings(tuple(unit_iris), tuple(unit_texts)).items()
        }

    def get_units(
        self,
        request: Request,
    ) -> list[Unit]:
        """Fetch all SI units"""
        return [
            make_unit(unit)
            for unit in get_all_units()
        ]
