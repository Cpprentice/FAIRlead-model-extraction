from typing import List
import urllib.parse

from fastapi import HTTPException, Request, Response
import pydot

from simpler_api.impl.plugins import get_cursor
from simpler_api.apis.schema_api_base import BaseSchemaApi
from simpler_api.impl.storage import get_storage
from simpler_api.models.model_schema import ModelSchema
from simpler_core.dot import create_graph


class SchemaApi(BaseSchemaApi):
    def get_all_schemas(
        self,
        request: Request,
        entity_prefix: str,
    ) -> List[ModelSchema]:
        storage = get_storage()
        return [
            ModelSchema(
                id=data_name
            )
            for data_name in storage.list_available_data()
        ]

    def get_schema_by_id(
        self,
        request: Request,
        schemaId: str,
        entity_prefix: str,
    ) -> ModelSchema:
        storage = get_storage()
        for data_name in storage.list_available_data():
            if data_name == schemaId:
                return ModelSchema(
                    id=data_name
                )
        raise HTTPException(status_code=404, detail="Schema not found")

    def get_schema_diagram(
        self,
        request: Request,
        schemaId: str,
        show_attributes: bool,
    ) -> str:

        cursor = get_cursor(request, schemaId)
        entities = cursor.get_all_entities()

        graph = create_graph(entities, show_attributes)

        requested_data_type = request.headers['accept']
        if requested_data_type == 'image/svg+xml':
            return Response(graph.create(prog=['dot', '-Kfdp'], format='svg'), media_type='image/svg+xml')
            # return graph.create(format='svg')
        return Response(graph.to_string(), media_type='text/plain')
