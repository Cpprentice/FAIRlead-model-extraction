import json
import re
import sys
from pathlib import Path
from typing import List, Dict

from datamodel_code_generator import generate, InputFileType, DataModelType, PythonVersion, load_yaml
from datamodel_code_generator.model import get_data_model_types, DataModel
from datamodel_code_generator.model.pydantic_v2 import RootModel

from simpler_core.cardinality import create_cardinality
from simpler_core.plugin import DataSourceType, DataSourcePlugin, EntityLink
from simpler_model import Entity, Attribute, Relation, EntityModifier


class JSONDataSourceType(DataSourceType):
    name = 'JSON'
    inputs = [
        'data',
        'schema'
    ]
    input_validation_statement = r'(data.*|schema.*)'


class JSONDataSourcePlugin(DataSourcePlugin):

    data_source_type = JSONDataSourceType()

    def _generate_model_from_json_data(self, schema_name: str):
        with self.storage.get_data(schema_name) as stream_lookup:
            data_content = stream_lookup['data'].read().decode('utf-8')

            obj = load_yaml(
                data_content
            )

        return self.generate_model_from_dict(obj)

    @staticmethod
    def generate_model_from_parsed_schema(models: List[DataModel]) -> List[Entity]:
        target_name_lookup = {
            model.path: model.class_name
            for model in models
        }
        entities = []
        for model in models:

            # if isinstance(model, RootModel):
            #     continue  # TODO find out how to handle this. It seems this happens for type aliases (e.g. EntityLink für str)

            relations = []
            attributes = []

            if not isinstance(model, RootModel):
                for field in model.fields:
                    if len(field.unresolved_types) == 0:
                        attributes.append(Attribute(
                            attribute_name=[field.name],
                            has_attribute_modifier=None
                        ))
                    else:
                        type_hint_string = field.type_hint.lower()
                        optional_match = re.match(r'optional\[(.*)]', type_hint_string)
                        type_hint_string_without_optional = type_hint_string
                        has_optional = False
                        if optional_match is not None:
                            has_optional = True
                            type_hint_string_without_optional = optional_match.group(1)
                        collection_match = re.match(
                            r'(collection|sequence|mutablesequence|set|mutableset|mapping|mutablemapping|'
                            r'list|deque|dict|ordereddict)(?:\[(.+)])?',
                            type_hint_string_without_optional
                        )
                        is_collection = collection_match is not None

                        object_cardinality_min = 1
                        object_cardinality_max = 1

                        if is_collection:
                            object_cardinality_max = sys.maxsize
                            object_cardinality_min = 0
                        if has_optional:
                            object_cardinality_min = 0

                        object_cardinality = (object_cardinality_min, object_cardinality_max)

                        target_path, = field.unresolved_types
                        relations.append(Relation(
                            relation_name=[field.name],
                            has_relation_modifier=None,
                            has_object_entity=target_name_lookup[target_path],
                            has_subject_entity=model.class_name,
                            object_cardinality=create_cardinality(object_cardinality),
                            subject_cardinality=create_cardinality((1, 1)),
                            has_attribute=[]
                        ))

            entities.append(Entity(
                entity_name=[model.class_name],
                has_attribute=attributes,
                is_subject_in_relation=relations,
                is_object_in_relation=[],
                # has_entity_modifier=None if model.path == '#' else [EntityModifier(entity_modifier='weak')]
                has_entity_modifier=None
            ))
        return entities

    @staticmethod
    def generate_model_from_dict(obj: Dict) -> List[Entity]:
        from genson import SchemaBuilder

        builder = SchemaBuilder()
        builder.add_object(obj)
        schema_text = json.dumps(builder.to_schema())

        data_model_types = get_data_model_types(DataModelType.PydanticV2BaseModel, PythonVersion.PY_312)
        from datamodel_code_generator.parser.jsonschema import JsonSchemaParser

        parser_class = JsonSchemaParser
        parser = parser_class(
            source=schema_text,
            data_model_type=data_model_types.data_model,
            data_model_root_type=data_model_types.root_model,
            data_model_field_type=data_model_types.field_model,
            data_type_manager_type=data_model_types.data_type_manager,
            # base_class=base_class,
            # additional_imports=additional_imports,
            # custom_template_dir=custom_template_dir,
            # extra_template_data=extra_template_data,
            # target_python_version=target_python_version,
            # dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
            # validation=validation,
            # field_constraints=field_constraints,
            # snake_case_field=snake_case_field,
            # strip_default_none=strip_default_none,
            # aliases=aliases,
            # allow_population_by_field_name=allow_population_by_field_name,
            # allow_extra_fields=allow_extra_fields,
            # apply_default_values_for_required_fields=apply_default_values_for_required_fields,
            # force_optional_for_required_fields=force_optional_for_required_fields,
            # class_name=class_name,
            # use_standard_collections=use_standard_collections,
            # base_path=input_.parent
            # if isinstance(input_, Path) and input_.is_file()
            # else None,
            # use_schema_description=use_schema_description,
            # use_field_description=use_field_description,
            # use_default_kwarg=use_default_kwarg,
            # reuse_model=reuse_model,
            # enum_field_as_literal=LiteralType.All
            # if output_model_type == DataModelType.TypingTypedDict
            # else enum_field_as_literal,
            # use_one_literal_as_default=use_one_literal_as_default,
            # set_default_enum_member=True
            # if output_model_type == DataModelType.DataclassesDataclass
            # else set_default_enum_member,
            # use_subclass_enum=use_subclass_enum,
            # strict_nullable=strict_nullable,
            # use_generic_container_types=use_generic_container_types,
            # enable_faux_immutability=enable_faux_immutability,
            # remote_text_cache=remote_text_cache,
            # disable_appending_item_suffix=disable_appending_item_suffix,
            # strict_types=strict_types,
            # empty_enum_field_name=empty_enum_field_name,
            # custom_class_name_generator=custom_class_name_generator,
            # field_extra_keys=field_extra_keys,
            # field_include_all_keys=field_include_all_keys,
            # field_extra_keys_without_x_prefix=field_extra_keys_without_x_prefix,
            # wrap_string_literal=wrap_string_literal,
            # use_title_as_name=use_title_as_name,
            # use_operation_id_as_name=use_operation_id_as_name,
            # use_unique_items_as_set=use_unique_items_as_set,
            # http_headers=http_headers,
            # http_ignore_tls=http_ignore_tls,
            # use_annotated=use_annotated,
            # use_non_positive_negative_number_constrained_types=use_non_positive_negative_number_constrained_types,
            # original_field_name_delimiter=original_field_name_delimiter,
            # use_double_quotes=use_double_quotes,
            # use_union_operator=use_union_operator,
            # collapse_root_models=collapse_root_models,
            # special_field_name_prefix=special_field_name_prefix,
            # remove_special_field_name_prefix=remove_special_field_name_prefix,
            # capitalise_enum_members=capitalise_enum_members,
            # keep_model_order=keep_model_order,
            # known_third_party=data_model_types.known_third_party,
            # custom_formatters=custom_formatters,
            # custom_formatters_kwargs=custom_formatters_kwargs,
            # use_pendulum=use_pendulum,
            # http_query_parameters=http_query_parameters,
            # treat_dots_as_module=treat_dots_as_module,
            # use_exact_imports=use_exact_imports,
            # **kwargs,
        )

        # generate(
        #     data_content,
        #     input_file_type=InputFileType.Json,
        #     output=Path(f'storage') / 'ig2-json' / 'test',
        #     output_model_type=DataModelType.PydanticV2BaseModel,
        #     target_python_version=PythonVersion.PY_312
        # )

        parser.parse_raw()
        models = parser.results
        return JSONDataSourcePlugin.generate_model_from_parsed_schema(models)

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        return self._generate_model_from_json_data(name)

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass
