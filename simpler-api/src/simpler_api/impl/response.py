from typing import Any

import yaml
from fastapi import Request, Response

from simpler_core.rdf import build_owl


def wrap_response_according_to_accept_header(request: Request, response: Any) -> Response:
    requested_data_type = request.headers['accept']
    if requested_data_type == 'application/x-yaml':
        yaml_string = yaml.safe_dump(response)
        return Response(yaml_string, media_type='application/x-yaml')
    elif requested_data_type == 'application/xml':
        return Response('xml support not yet implemented', status_code=500, media_type='text/plain')
    elif requested_data_type == 'text/turtle':
        owl_string = build_owl(response, f'{request.url}/')  # TODO consider a better way to get the URL. We might miss the "entities" path part
        return Response(owl_string, media_type='text/turtle')
    else:
        return response
