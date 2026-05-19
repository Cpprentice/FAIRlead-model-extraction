import json
from typing import List
import urllib.parse

import yaml
from fastapi import HTTPException, Request, Response, Query
import pydot
from jsonasobj2 import JsonObj
from linkml_runtime import SchemaView
from linkml_runtime.utils.yamlutils import as_yaml
from yaml import SafeDumper

from fairlead_core.caching import DiskCache, Pipeline
from fairlead_core.metadata import convert_schema_to_oemetadata
from fairlead_core.partitioning import create_filtered_class_list
from fairlead_core.plugin import InputDataError
from simpler_api.impl.mapping import make_class_definition_view
from simpler_api.impl.plugins import get_cursor
from simpler_api.apis.schema_api_base import BaseSchemaApi
from simpler_api.impl.response import wrap_response_according_to_accept_header
from simpler_api.impl.storage import get_storage
from simpler_api.models.model_schema import ModelSchema
from fairlead_core.dot import create_graph, filter_graph
from fairlead_core.schema import apply_schema_correction_if_available, introduce_inverse_relations, \
    apply_schema_enhancement, load_schema_enhancement
from simpler_model import ClassDefinitionView


class SchemaApi(BaseSchemaApi):
    def get_all_schemas(
            self,
            request: Request,
            prevent_optimization: bool,
            prevent_automatic_optimization: bool,
            prevent_user_optimization: bool,
            generate_inverse_relations: bool,
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
            prevent_optimization: bool,
            prevent_automatic_optimization: bool,
            prevent_user_optimization: bool,
            generate_inverse_relations: bool,
    ) -> ModelSchema:
        storage = get_storage()
        for data_name in storage.list_available_data():
            if data_name == schemaId:
                return wrap_response_according_to_accept_header(request, ModelSchema(
                    id=data_name
                ))
        raise HTTPException(status_code=404, detail="Schema not found")

    def get_schema_diagram(
            self,
            request: Request,
            schemaId: str,
            show_attributes: bool,
            selected_entities: List[str],
            render_distance: int,
            prevent_optimization: bool,
            prevent_automatic_optimization: bool,
            prevent_user_optimization: bool,
            generate_inverse_relations: bool,
    ) -> str:
        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        entities = cursor.get_all_entities()

        graph = create_graph(entities, show_attributes)
        if len(selected_entities) > 0:
            graph = filter_graph(graph, selected_entities, render_distance)
            if graph is None:
                raise HTTPException(status_code=400, detail='Selected Filtering entity does not exist')

        requested_data_type = request.headers['accept']
        if requested_data_type == 'image/svg+xml':
            return Response(graph.create(prog=['dot', '-Kfdp'], format='svg'), media_type='image/svg+xml')
        return Response(graph.to_string(), media_type='text/plain')

    def get_classes_by_schema(
        self,
        request: Request,
        schemaId: str,
        prevent_structural_enhancement: bool,
        prevent_enhancement: bool,
        class_filter: list[str]
    ) -> list[ClassDefinitionView] | Response:
        """desc"""

        hash_reset_depth = int(request.query_params.get('_hash_reset', 0))

        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        with cursor.get_cache(hash_reset_depth) as cache:

            pipeline = Pipeline(cache)

            @pipeline.operation([
                prevent_structural_enhancement,
                prevent_enhancement
            ])
            def get_schema():
                try:
                    return cursor.get_schema()
                except InputDataError as ex:
                    raise HTTPException(
                        status_code=400,
                        detail="Schema extraction failed due to invalid input data"
                    ) from ex

            @pipeline.operation([
                class_filter
            ])
            def filter_schema(schema):
                if class_filter:
                    return create_filtered_class_list(schema, class_filter, 1)
                return schema

            @pipeline.operation([
                request.headers['accept']
            ])
            def produce_response(schema):
                if request.headers['accept'] == 'application/x.linkml+yaml':
                    def json_obj_representer(dumper: SafeDumper, data: JsonObj):
                        return dumper.represent_mapping(
                            "tag:yaml.org,2002:map",
                            data._as_dict
                        )

                    yaml.SafeDumper.add_representer(
                        JsonObj,
                        json_obj_representer
                    )
                    return Response(as_yaml(schema), media_type='application/x.linkml+yaml')
                elif request.headers['accept'] == 'application/x.oemeta+json':
                    oemeta_dict = convert_schema_to_oemetadata(schema)
                    oemeta = json.dumps(oemeta_dict, indent=4)
                    return Response(oemeta, media_type='application/x.oemeta+json')

                schema_view = SchemaView(schema)
                view_classes = [
                    make_class_definition_view(class_def, schema_view)
                    for class_def in schema.classes.values()
                ]

                return wrap_response_according_to_accept_header(request, view_classes)

            return pipeline.run()

            # response = cache.get_next([
            #     schemaId,
            #     prevent_structural_enhancement,
            #     prevent_enhancement,
            #     class_filter,
            #     request.headers['accept']
            # ])
            # if response is not None:
            #     return response
            #
            # filtered_schema = cache.get_next([class_filter])
            # if filtered_schema is not None:

            try:
                schema = cursor.get_schema()
            except InputDataError as ex:
                raise HTTPException(status_code=400, detail="Schema extraction failed due to invalid input data") from ex


            if class_filter:
                 schema = create_filtered_class_list(schema, class_filter, 1)
            # # create_nx_graph_from_entity_list(entities)
            # introduce_api_urls_to_entity_list(entities, request, schemaId)



            if request.headers['accept'] == 'application/x.linkml+yaml':
                def json_obj_representer(dumper: SafeDumper, data: JsonObj):
                    return dumper.represent_mapping(
                        "tag:yaml.org,2002:map",
                        data._as_dict
                    )

                yaml.SafeDumper.add_representer(
                    JsonObj,
                    json_obj_representer
                )
                return Response(as_yaml(schema), media_type='application/x.linkml+yaml')
            elif request.headers['accept'] == 'application/x.oemeta+json':
                oemeta_dict = convert_schema_to_oemetadata(schema)
                oemeta = json.dumps(oemeta_dict, indent=4)
                return Response(oemeta, media_type='application/x.oemeta+json')

            schema_view = SchemaView(schema)
            view_classes = [
                make_class_definition_view(class_def, schema_view)
                for class_def in schema.classes.values()
            ]

            return wrap_response_according_to_accept_header(request, view_classes)
