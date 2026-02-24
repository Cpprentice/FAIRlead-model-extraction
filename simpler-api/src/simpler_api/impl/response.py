from typing import Any

import yaml
from fastapi import Request, Response
from linkml_runtime.utils.yamlutils import as_yaml

from fairlead_core.linkml_schema import convert_er_to_linkml
from fairlead_core.rdf import build_owl


def wrap_response_according_to_accept_header(request: Request, response: Any) -> Response:
    if 'accept' not in request.headers:
        return response
    requested_data_type = request.headers['accept']
    if requested_data_type == 'application/x-yaml':
        yaml_string = yaml.safe_dump(response)
        return Response(yaml_string, media_type='application/x-yaml')
    elif requested_data_type == 'application/xml':
        return Response('xml support not yet implemented', status_code=500, media_type='text/plain')
    elif requested_data_type == 'text/turtle':
        owl_string = build_owl(response, f'{request.url}/')  # TODO consider a better way to get the URL. We might miss the "entities" path part
        return Response(owl_string, media_type='text/turtle')
    elif requested_data_type == 'application/x.linkml+yaml':
        schema = convert_er_to_linkml(response)
        return Response(as_yaml(schema), media_type='application/x.linkml+yaml')
    elif requested_data_type == 'application/x.oemeta+json':
        oemeta = '...'  # TODO convert to oemeta
        # return Response(oemeta, media_type='application/x.oemeta+json')
        return response
    else:
        return response
