from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND

from simpler_api.apis.semantics_api_base import BaseSemanticsApi


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