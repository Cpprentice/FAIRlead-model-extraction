from typing import List
import urllib.parse

from fastapi import HTTPException, Request, Response
import pydot

from simpler_api.impl.plugins import get_cursor
from simpler_api.apis.schema_api_base import BaseSchemaApi
from simpler_api.impl.storage import get_storage
from simpler_api.models.model_schema import ModelSchema


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
        pass

    def get_schema_diagram(
        self,
        request: Request,
        schemaId: str,
        show_attributes: bool,
    ) -> str:
        graph = pydot.Dot(f'{schemaId}_graph', graph_type='graph')
        graph.set_fontname("Helvetica,Arial,sans-serif")
        graph.add_node(pydot.Node('node', fontname='Helvetica,Arial,sans-serif'))
        graph.add_node(pydot.Node('edge', fontname='Helvetica,Arial,sans-serif'))

        cursor = get_cursor(request, schemaId)
        entities = cursor.get_all_entities()
        border_count = {'weak': 2, 'strong': 1}
        relation_border_count = {True: 2, False: 1}

        for entity in entities:
            graph.add_node(pydot.Node(entity.name, shape='box', peripheries=border_count[entity.type]))
            for related_entity in entity.related_entities:
                sorted_relative_names = sorted([entity.name, related_entity.name])
                relation_name = f'#{related_entity.relation_name}#'.join(sorted_relative_names)
                graph.add_node(pydot.Node(relation_name, label=related_entity.relation_name, shape='diamond',
                                          style='filled', fillcollor='lightgrey',
                                          peripheries=relation_border_count[related_entity.is_identifying]))
                graph.add_edge(pydot.Edge(entity.name, relation_name, label=related_entity.cardinalities[1]))
                graph.add_edge(pydot.Edge(related_entity.name, relation_name, label=related_entity.cardinalities[0]))
            if show_attributes:
                for attribute in entity.attributes:
                    attribute_id = f'{entity.name}#{attribute.name}'
                    attribute_label = attribute.name
                    if attribute.is_key:
                        attribute_label = f'<<u>{attribute_label}</u>>'
                    graph.add_node(pydot.Node(attribute_id, label=attribute_label, shape='ellipse'))
                    graph.add_edge(pydot.Edge(entity.name, attribute_id))

        requested_data_type = request.headers['accept']
        if requested_data_type == 'image/svg+xml':
            return Response(graph.create(prog=['dot', '-Kfdp'], format='svg'), media_type='image/svg+xml')
            # return graph.create(format='svg')
        return Response(graph.to_string(), media_type='text/plain')
