import urllib.request
from typing import List

from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import get_data_model_types

from simpler_core.cardinality import create_cardinality
from simpler_core.plugin import DataSourceType, DataSourcePlugin, EntityLink
from simpler_model import Entity, Attribute, Relation, EntityModifier
from simpler_plugin_json import JSONDataSourcePlugin


class OpenApiDataSourceType(DataSourceType):
    name = 'OpenAPI'
    inputs = [
        'spec_file',
        'spec_url'
    ]
    input_validation_statement = r'(spec_file|spec_url)'


class OpenApiDataSourcePlugin(DataSourcePlugin):
    data_source_type = OpenApiDataSourceType()

    def _create_schema(self, name: str):

        source = ''

        with self.storage.get_data(name) as stream_lookup:
            if 'spec_file' in stream_lookup:
                openapi_spec_json_string = stream_lookup['spec_file'].read().decode('utf-8')
                source = openapi_spec_json_string
            elif 'spec_url' in stream_lookup:
                openapi_spec_url = stream_lookup['spec_url'].read().decode('utf-8')
                response = urllib.request.urlopen(openapi_spec_url)
                source = response.read().decode()

        data_model_types = get_data_model_types(DataModelType.PydanticV2BaseModel, PythonVersion.PY_312)
        from datamodel_code_generator.parser.openapi import OpenAPIParser

        parser = OpenAPIParser(
            source=source,
            data_model_type=data_model_types.data_model,
            data_model_root_type=data_model_types.root_model,
            data_model_field_type=data_model_types.field_model,
            data_type_manager_type=data_model_types.data_type_manager,
            # base_class: Optional[str] = None,
            # additional_imports: Optional[List[str]] = None,
            # custom_template_dir: Optional[Path] = None,
            # extra_template_data: Optional[DefaultDict[str, Dict[str, Any]]] = None,
            # target_python_version: PythonVersion = PythonVersion.PY_37,
            # dump_resolve_reference_action: Optional[Callable[[Iterable[str]], str]] = None,
            # validation: bool = False,
            # field_constraints: bool = False,
            # snake_case_field: bool = False,
            # strip_default_none: bool = False,
            # aliases: Optional[Mapping[str, str]] = None,
            # allow_population_by_field_name: bool = False,
            # allow_extra_fields: bool = False,
            # apply_default_values_for_required_fields: bool = False,
            # force_optional_for_required_fields: bool = False,
            # class_name: Optional[str] = None,
            # use_standard_collections: bool = False,
            # base_path: Optional[Path] = None,
            # use_schema_description: bool = False,
            # use_field_description: bool = False,
            # use_default_kwarg: bool = False,
            # reuse_model: bool = False,
            # encoding: str = 'utf-8',
            # enum_field_as_literal: Optional[LiteralType] = None,
            # use_one_literal_as_default: bool = False,
            # set_default_enum_member: bool = False,
            # use_subclass_enum: bool = False,
            # strict_nullable: bool = False,
            # use_generic_container_types: bool = False,
            # enable_faux_immutability: bool = False,
            # remote_text_cache: Optional[DefaultPutDict[str, str]] = None,
            # disable_appending_item_suffix: bool = False,
            # strict_types: Optional[Sequence[StrictTypes]] = None,
            # empty_enum_field_name: Optional[str] = None,
            # custom_class_name_generator: Optional[Callable[[str], str]] = None,
            # field_extra_keys: Optional[Set[str]] = None,
            # field_include_all_keys: bool = False,
            # field_extra_keys_without_x_prefix: Optional[Set[str]] = None,
            # openapi_scopes: Optional[List[OpenAPIScope]] = None,
            # wrap_string_literal: Optional[bool] = False,
            # use_title_as_name: bool = False,
            # use_operation_id_as_name: bool = False,
            # use_unique_items_as_set: bool = False,
            # http_headers: Optional[Sequence[Tuple[str, str]]] = None,
            # http_ignore_tls: bool = False,
            # use_annotated: bool = False,
            # use_non_positive_negative_number_constrained_types: bool = False,
            # original_field_name_delimiter: Optional[str] = None,
            # use_double_quotes: bool = False,
            # use_union_operator: bool = False,
            # allow_responses_without_content: bool = False,
            # collapse_root_models: bool = False,
            # special_field_name_prefix: Optional[str] = None,
            # remove_special_field_name_prefix: bool = False,
            # capitalise_enum_members: bool = False,
            # keep_model_order: bool = False,
            # known_third_party: Optional[List[str]] = None,
            # custom_formatters: Optional[List[str]] = None,
            # custom_formatters_kwargs: Optional[Dict[str, Any]] = None,
            # use_pendulum: bool = False,
            # http_query_parameters: Optional[Sequence[Tuple[str, str]]] = None,
            # treat_dots_as_module: bool = False,
            # use_exact_imports: bool = False,
        )
        parser.parse_raw()
        models = parser.results
        return JSONDataSourcePlugin.generate_model_from_parsed_schema(models)

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        return self._create_schema(name)

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass


class WsdlDataSourceType(DataSourceType):
    name = 'WSDL'
    inputs = [
        'spec'
    ]
    input_validation_statement = r'spec'


class WsdlDataSourcePlugin(DataSourcePlugin):
    data_source_type = WsdlDataSourceType()

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        pass

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass
