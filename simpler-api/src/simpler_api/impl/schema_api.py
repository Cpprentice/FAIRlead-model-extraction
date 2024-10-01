from typing import List
import urllib.parse

from fastapi import HTTPException, Request, Response
import pydot

from simpler_api.impl.plugins import get_cursor
from simpler_api.apis.schema_api_base import BaseSchemaApi
from simpler_api.impl.storage import get_storage
from simpler_api.models.model_schema import ModelSchema
from simpler_core.dot import create_graph, filter_graph
from simpler_core.schema import apply_schema_correction_if_available, introduce_inverse_relations


class SchemaApi(BaseSchemaApi):
    def get_all_schemas(
        self,
        request: Request,
    ) -> List[ModelSchema]:
        storage = get_storage()
        return [
            ModelSchema(
                id=data_name,
                implementation=storage.get_plugin_name(data_name)
            )
            for data_name in storage.list_available_data()
        ]

    def get_schema_by_id(
        self,
        request: Request,
        schemaId: str,
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
        selected_entities: List[str],
        render_distance: int,
        generate_inverse_relations: bool,
    ) -> str:
        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        entities = cursor.get_all_entities()

        entities = apply_schema_correction_if_available(entities, get_storage(), schemaId)
        if generate_inverse_relations:
            introduce_inverse_relations(entities)

        graph = create_graph(entities, show_attributes)
        if len(selected_entities) > 0:
            graph = filter_graph(graph, selected_entities, render_distance)

        requested_data_type = request.headers['accept']
        if requested_data_type == 'image/svg+xml':
            return Response(graph.create(prog=['dot', '-Kfdp'], format='svg'), media_type='image/svg+xml')
            # return graph.create(format='svg')
        return Response(graph.to_string(), media_type='text/plain')
