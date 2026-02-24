import collections
import io
import json
from typing import List
import urllib.request
import urllib.response

from jsonpath import JSONPath
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

from simpler_core.cardinality import create_cardinality
from simpler_core.plugin import DataSourceType, InputFlag, DataSourcePlugin, EntityLink
from simpler_model import Entity, Attribute, AttributeModifier, Relation


class LinkmlDataSourceType(DataSourceType):
    name = 'Linkml'
    inputs = [
        ('schema', InputFlag.TEXT | InputFlag.SHOW_IN_JSON),
        ('data', InputFlag.TEXT)
    ]
    input_validation_statement = r'schema'


class LinkmlDataSourcePlugin(DataSourcePlugin):
    data_source_type = LinkmlDataSourceType()

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        with self.storage.get_data(name) as stream_lookup:
            schema_text = io.TextIOWrapper(stream_lookup['schema'], encoding='utf-8').read()
            schema_view = SchemaView(schema_text)

        schema_index = schema_view.usage_index()
        all_class_names = set(schema_view.all_classes())
        filtered_schema_index = {
            k: v
            for k, v in schema_index.items()
            if k in all_class_names
        }

        tree_root_class_names = [
            class_name
            for class_name, class_ in schema_view.all_classes().items()
            if class_.tree_root
        ]
        if len(tree_root_class_names) == 0:
            tree_root_class_names = all_class_names - set(filtered_schema_index)

        json_path_expressions = collections.defaultdict(list)
        for root_class_name in tree_root_class_names:
            json_path_expressions[root_class_name].append('$')

        while len(filtered_schema_index) > 0:

            removals = []
            for class_name, usages in filtered_schema_index.items():
                for usage in usages:
                    if usage.used_by in json_path_expressions:
                        slot = schema_view.induced_slot(usage.slot, usage.used_by)
                        for parent_expression in json_path_expressions[usage.used_by]:
                            if slot.multivalued:
                                # the following will select also other classes if the list is built with anyOf
                                json_path_expressions[class_name].append(f'{parent_expression}.{usage.slot}[:]')
                            else:
                                json_path_expressions[class_name].append(f'{parent_expression}.{usage.slot}')
                        removals.append((class_name, usage))

            for key, usage in removals:
                filtered_schema_index[key].remove(usage)

                if len(filtered_schema_index[key]) == 0:
                    del filtered_schema_index[key]

        entities = []
        # root_class = None
        for class_id, class_ in schema_view.all_classes().items():

            # if class_.tree_root:
            #     if root_class is not None:
            #         raise ValueError('The schema has multiple tree_root classes')
            #     root_class = class_

            attributes = []
            relations = []
            for slot in class_.slots:
                ranged_items = [slot]
                if slot.any_of is not None and len(slot.any_of) > 0:
                    ranged_items = slot.any_of

                for ranged_item in ranged_items:
                    if ranged_item.range in {'string', 'integer', 'float', 'double', 'jsonpath',}:
                        # only for primitive slots
                        if len(attributes) > 0 and attributes[-1].attribute_name[0] != slot.name:
                            # Attributes are not duplicated with multiple primitive types
                            attributes.append(Attribute(
                                attribute_name=[slot.name],
                                has_attribute_modifier=[] if not slot.identifier else [
                                    AttributeModifier(attribute_modifier='key')
                                ]
                            ))
                    else:
                        # only for non-primitive slots - this can have multiple relations with
                        #  the same name and different range
                        relations.append(Relation(
                            relation_name=[slot.name],
                            has_subject_entity=slot.domain,
                            has_object_entity=ranged_item.range,
                            has_relation_modifier=None,
                            subject_cardinality=create_cardinality((1, 1)),
                            object_cardinality=create_cardinality((slot.minimum_cardinality, slot.maximum_cardinality))
                        ))

            entities.append(Entity(
                entity_name=[class_id],
                has_entity_modifier=None,
                is_subject_in_relation=relations,
                has_attribute=attributes,
                mapping_text=json_path_expressions[class_id][0]  # TODO add support for more than one jsonpath
            ))

        # TODO collect all jsonpaths to each entity (does obviously not work when reading rdf data - for csv we can use the linkml container pattern)

        return entities

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass

    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:

        data_format = 'json'  # get this from the plugin file maybe?

        entities = self.get_all_entities(name)
        target_entity = [x for x in entities if x.entity_name[0] == entity_id][0]

        with self.storage.get_data(name) as stream_lookup:
            if 'data' in stream_lookup:
                data_stream = stream_lookup['data']
                # parse data and then select the entities

                result_data = None
                mime_type = None
                if data_format == 'json':
                    mime_type = 'application/json'
                    data = json.load(data_stream)
                    query = JSONPath(target_entity.mapping_text)
                    result_data = query.parse(data)

                return result_data, mime_type
        return None, ''
