import collections
import io
import json
import sys
from contextlib import suppress
from types import NoneType
from typing import BinaryIO, List, TextIO, Tuple, Sequence, get_origin, get_args, Any, Dict, Annotated, Union

import rdflib
import yaml
from pydantic import BaseModel, BaseConfig, PydanticUndefinedAnnotation, create_model, ValidationError
from pydantic.v1.utils import deep_update
from pydantic_core.core_schema import ModelField
from pydantic_partial import create_partial_model
from pydantic_partial._compat import PydanticCompat
from rdflib import Namespace

from simpler_core.cardinality import create_cardinality
from simpler_core.rdf import build_graph
from simpler_core.storage import DataSourceStorage
from simpler_model import Entity, Attribute

try:
    from simpler_model import Relation
    EntityLink = Relation
except ImportError:
    from simpler_model import EntityLink
    Relation = EntityLink

schema_correction_file_name = 'schema-correction'


def apply_schema_correction_if_available(
        entities: List[Entity],
        storage: DataSourceStorage,
        schema_name: str
) -> List[Entity]:
    with storage.get_data(schema_name) as stream_lookup:
        if schema_correction_file_name in stream_lookup:
            return extend_schema_from_yaml(entities, stream_lookup[schema_correction_file_name])
    return entities


def load_external_schema_from_yaml(binary_stream: BinaryIO) -> List[Entity]:
    entity_data_list = yaml.safe_load(binary_stream)
    return [
        Entity.from_dict(entity_data)
        for entity_data in entity_data_list
    ]


def load_external_schema_from_json(text_stream: TextIO) -> List[Entity]:
    entity_data_list = json.load(text_stream)
    return [
        Entity.from_dict(entity_data)
        for entity_data in entity_data_list
    ]


optional_field_exceptions = {
    'PartialEntity': ['entity_name'],
    'PartialRelation': ['relation_name'],
    'PartialAttribute': ['attribute_name']
}


# This class is based on https://github.com/pydantic/pydantic/discussions/3089
#  but is extended to support the exclusion of specified fields when making everything optional
class OptionalModel(BaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)

        for field_name, field in cls.model_fields.items():
            if cls.__name__ not in optional_field_exceptions \
                    or field_name not in optional_field_exceptions[cls.__name__]:
                field.annotation = field.annotation | None  # <- for valid JsonSchema
                field.default = None
            else:
                # we want to allow None as a value in the List of names to handle deletions
                strict_modifier = field.annotation.__args__[0].__metadata__[0]
                field.annotation.__args__ = (Annotated[Union[str, None], strict_modifier],)

        with suppress(PydanticUndefinedAnnotation):
            cls.model_rebuild(force=True)


def make_optional(base_class: type[BaseModel]) -> type:
    return create_model(f'Partial{base_class.__name__}', __base__=(base_class, OptionalModel))


class PartialEntity(Entity, OptionalModel):
    pass


# class PartialRelation(Relation, OptionalModel):
#     pass

PartialRelation = make_optional(Relation)
PartialAttribute = make_optional(Attribute)

# PartialEntity = create_partial_model(Entity, recursive=True)
# PartialRelation = create_partial_model(Relation, recursive=True)

replacements = {
    Relation: PartialRelation,
    Attribute: PartialAttribute
}


def iterate_and_replace_annotation(annotation):
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is None:
        for base, target in replacements.items():
            if annotation is base:
                annotation = target
        return annotation
    if origin is NoneType:
        return NoneType

    return origin[tuple(iterate_and_replace_annotation(arg) for arg in args)]


def replace_annotations(partial_class: type[BaseModel]):
    model_compat = PydanticCompat(partial_class)
    # fields_ = list(model_compat.model_fields.keys())
    for field_name, field_info in model_compat.model_fields.items():
        field_annotation = model_compat.get_model_field_info_annotation(field_info)
        new_field_annotation = iterate_and_replace_annotation(field_annotation)
        field_info.annotation = new_field_annotation
    _ = 42
    partial_class.model_rebuild(force=True)


replace_annotations(PartialEntity)


def load_partial_schema_from_yaml(binary_stream: BinaryIO) -> List[PartialEntity]:
    entity_data_list = yaml.safe_load(binary_stream)
    if entity_data_list is None:
        return []
    return [
        PartialEntity.model_validate(entity_extension_data)
        for entity_extension_data in entity_data_list
    ]
    # return [
    #     PartialEntity.from_dict(entity_data)
    #     for entity_data in entity_data_list
    # ]


def serialize_partial_schema_to_yaml(entities: list[PartialEntity], target_stream: TextIO = None) -> str | None:
    dicts = [m.model_dump(exclude={'additional_properties'}, exclude_defaults=True, by_alias=True) for m in entities]
    return yaml.safe_dump(dicts, target_stream)


def get_user_schema_correction(schema_name: str, storage: DataSourceStorage) -> list[PartialEntity]:
    with storage.get_data(schema_name) as stream_lookup:
        if schema_correction_file_name in stream_lookup:
            return load_partial_schema_from_yaml(stream_lookup[schema_correction_file_name])
    return []


def extend_schema_from_yaml(entities: List[Entity], binary_stream: BinaryIO) -> List[Entity]:
    entity_extension_data_list = yaml.safe_load(binary_stream)
    if entity_extension_data_list is None:
        return entities
    partial_entities = [
        PartialEntity.model_validate(entity_extension_data)
        for entity_extension_data in entity_extension_data_list
    ]

    entity_dict_list = [x.model_dump() for x in entities]
    update_dict_list = [x.model_dump(exclude_defaults=True) for x in partial_entities]

    # A first attempt was using the deep_merge function from pydantic
    #  However, updating a dict will never properly work for the merging of entities with name overwrites
    #  as the names are not keys of the dict but stored in lists. The following implementation attempts to
    #  honor the name overwrite pattern accordingly
    merged_dict_list = merge_schema_lists(entity_dict_list, update_dict_list)

    original_entity_lookup = {
        tuple(entity_data['entity_name']): entity
        for entity_data in merged_dict_list
        for entity in entities
        if is_super_set_of(entity.entity_name, entity_data['entity_name'])
    }

    # TODO we might need to change this back
    result_entities = []
    original_entities_added = set()
    for entity_data in merged_dict_list:
        try:
            entity = Entity(**entity_data)
            result_entities.append(entity)
        except ValidationError:
            entity = original_entity_lookup[tuple(entity_data['entity_name'])]
            entity_name_tuple = tuple(entity.entity_name)
            if entity_name_tuple not in original_entities_added:
                result_entities.append(entity)
                original_entities_added.add(entity_name_tuple)
    # result_entities = [Entity(**x) for x in merged_dict_list]
    return result_entities


def serialize_entity_list_to_yaml(entities: List[Entity], target_stream: TextIO = None) -> str | None:
    dicts = [m.model_dump(exclude={'additional_properties'}, exclude_defaults=True, by_alias=True) for m in entities]
    return yaml.safe_dump(dicts, target_stream)


def serialize_entity_list_to_json(entities: List[Entity], target_stream: TextIO = None) -> str | None:
    dicts = [m.model_dump(exclude={'additional_properties'}) for m in entities]
    if target_stream is None:
        return json.dumps(dicts, indent=4)
    json.dump(dicts, target_stream, indent=4)


# We want to introduce a mechanism to update the automatically extracted schema with user input - which should
#  use exactly the same data structure - it would be good though if a partial object is also allowed, such that
#  only necessary parts are overwritten.
#  In general the following updates are thinkable:
#  - add entity
#  - rename entity
#  - replace entity modifier

#  - add relation
#  - rename relation
#  - replace relation modifier
#  - replace relation cardinality

#  - add attribute
#  - rename attribute
#  - replace attribute modifier

#  - remove relation (not supported)
#  - remove entity (not supported)
#  - remove attribute (not supported)


def is_super_set_of(base_set: Sequence[str], super_set: Sequence[str]) -> bool:
    return all(x in super_set for x in base_set)


def get_precedence_keys(name_lists: List[List[Sequence[str]]]) -> List[Tuple[str, ...]]:
    tuple_list_lists = [
        [
            tuple(inner)
            for inner in outer
        ]
        for outer in name_lists
    ]

    if len(tuple_list_lists) == 1:
        return tuple_list_lists[0]

    while len(tuple_list_lists) > 1:
        left_name_lists = tuple_list_lists[0]
        right_name_lists = tuple_list_lists[1]

        new_name_list = []
        for left_name_tuple in left_name_lists:
            has_override = False
            for right_name_tuple in right_name_lists:
                if is_super_set_of(left_name_tuple, right_name_tuple):
                    # this is an override
                    has_override = True
                    if right_name_tuple not in new_name_list:
                        new_name_list.append(right_name_tuple)
                    break
            if not has_override:
                new_name_list.append(left_name_tuple)
        for right_name_tuple in right_name_lists:
            if right_name_tuple not in new_name_list:
                new_name_list.append(right_name_tuple)
        tuple_list_lists = [new_name_list, *tuple_list_lists[2:]]
    return tuple_list_lists[0]


def get_precedence_keys_from_objects(iterables: List[List], key_attribute: str) -> List[Tuple[str, ...]]:
    """
    This method expects a set of lists of objects that all have the key attribute which is in turn a list

    Parameters
    ----------
    iterables
    key_attribute

    Returns
    -------

    """

    name_lists = [[getattr(x, key_attribute) for x in iterable] for iterable in iterables]
    return get_precedence_keys(name_lists)


def get_precedence_keys_from_dicts(iterables: List[List], key: str) -> List[Tuple[str, ...]]:
    return get_precedence_keys([[x.get(key) for x in iterable] for iterable in iterables])


def get_name_key(item_list: List) -> str | None:
    first = item_list[0]
    if not isinstance(first, dict):
        return None
    name_keys = [key for key in first.keys() if key.endswith('_name')]
    if len(name_keys) == 0:
        return None
    return name_keys[0]


def merge_schema_lists(base_list: List, update_list: List, no_deletes=False) -> List:
    if len(base_list) == 0:
        return update_list
    name_key = get_name_key(base_list)
    if name_key is None:
        return update_list
    keys = get_precedence_keys_from_dicts([base_list, update_list], name_key)
    lookup = collections.defaultdict(list)
    for key in keys:
        for x in base_list:
            if is_super_set_of(x[name_key], key):
                lookup[key].append(x)
        for x in update_list:
            if is_super_set_of(x[name_key], key):
                lookup[key].append(x)

    result_list = []
    for key, items in lookup.items():
        if len(items) == 1:
            result_list.append(items[0])
            continue
        deletion = False
        while len(items) > 1:
            base = items[0]
            update = items[1]
            result = merge_schema_dicts(base, update, no_deletes)
            if result[name_key][0] is None and not no_deletes:
                deletion = True
                items = []
            else:
                items = [result, *items[2:]]
        if not deletion:
            result_list.append(items[0])
    return result_list


def multi_merge_schema_lists(item_lists: list[list], no_deletes=False) -> List:
    non_empty_item_lists = [item_list for item_list in item_lists if item_list]
    if len(non_empty_item_lists) == 1:
        return non_empty_item_lists[0]
    if len(non_empty_item_lists) == 0:
        return []

    name_key = get_name_key(non_empty_item_lists[0])
    if name_key is None:
        # this does simply represent lists and not named concepts - since the input should be already ordered we just
        #  return the last value
        return item_lists[-1]
    keys = get_precedence_keys_from_dicts(non_empty_item_lists, name_key)

    # Can we already infer an order from this?
    lookup = collections.defaultdict(list)
    for key in keys:
        for item_list in non_empty_item_lists:
            for item in item_list:
                if is_super_set_of(item[name_key], key):
                    lookup[key].append(item)

    result_list = []
    for key, items in lookup.items():
        if len(items) == 1:
            result_list.append(items[0])
            continue
        items.sort(key=lambda x: len(x[name_key]))  # this should sort changes according to apply order
        deletion = False
        result = multi_merge_schema_dicts(items, no_deletes)
        if result[name_key][0] is None and not no_deletes:
            deletion = True
        # while len(items) > 1:
        #     base = items[0]
        #     update = items[1]
        #     result = multi_merge_schema_dicts(base, update, no_deletes)
        #     if result[name_key][0] is None and not no_deletes:
        #         deletion = True
        #         items = []
        #     else:
        #         items = [result, *items[2:]]
        if not deletion:
            result_list.append(result)
    return result_list


def introduce_inverse_relations(entities: List[Entity]):
    # TODO shouldn't we model this with some kine of reasoning instead?
    entity_lookup = {
        entity.entity_name[0]: entity
        for entity in entities
    }
    for entity in entities:
        for relation in entity.is_subject_in_relation:
            if relation.inverse_relation is None:
                try:
                    target_entity = entity_lookup[relation.has_object_entity]
                except KeyError:
                    # TODO make sure this produces a model error or warning
                    continue
                inverse_relation = Relation(
                    has_object_entity=entity.entity_name[0],
                    has_subject_entity=target_entity.entity_name[0],
                    object_cardinality=relation.subject_cardinality,
                    subject_cardinality=relation.object_cardinality,
                    relation_name=[f'-{relation.relation_name[0]}'],
                    has_attribute=relation.has_attribute,
                    has_relation_modifier=[],
                    inverse_relation=relation.relation_name[0]
                )
                relation.inverse_relation=inverse_relation.relation_name[0]
                if target_entity.is_object_in_relation is None:
                    target_entity.is_object_in_relation = []
                target_entity.is_object_in_relation.append(relation)
                target_entity.is_subject_in_relation.append(inverse_relation)
                if entity.is_object_in_relation is None:
                    entity.is_object_in_relation = []
                entity.is_object_in_relation.append(inverse_relation)


def merge_schema_dicts(base_dict: Dict, update_dict: Dict, no_deletes=False) -> Dict:
    result = {}
    for key, original_value in base_dict.items():
        if key in update_dict:
            if original_value is None:
                result[key] = update_dict[key]
            elif isinstance(original_value, list):
                result[key] = merge_schema_lists(original_value, update_dict[key], no_deletes)
            elif isinstance(original_value, dict):
                result[key] = merge_schema_dicts(original_value, update_dict[key], no_deletes)
            else:
                result[key] = update_dict[key]
        else:
            result[key] = original_value
    for key, update_value in update_dict.items():
        if key not in result:
            result[key] = update_value
    return result


def _remove_consecutive_duplicates(items: list) -> list:
    if not items:
        return items
    result = [items[0]]
    for item in items[1:]:
        if item != result[-1]:
            result.append(item)
    return result


def multi_merge_schema_dicts(dictionaries: list[dict], no_deletes=False) -> dict:
    result = {}
    combined_key_set = {key for schema_dict in dictionaries if schema_dict is not None for key in schema_dict.keys()}
    for key in combined_key_set:
        values = [
            schema_dict[key]
            for schema_dict in dictionaries
            if schema_dict is not None
            and key in schema_dict
        ]
        values = _remove_consecutive_duplicates(values)
        if len(values) == 1:
            result[key] = values[0]
        elif any(isinstance(value, list) for value in values):
            result[key] = multi_merge_schema_lists(values, no_deletes)
        elif any(isinstance(value, dict) for value in values):
            result[key] = multi_merge_schema_dicts(values, no_deletes)
        else:
            # in this case we do have scalar values that can not be "deleted" so we use the last non falsy value
            non_falsy_values = [x for x in values if x]
            result[key] = non_falsy_values[-1] if len(non_falsy_values) > 0 else None
            # values = _remove_consecutive_duplicates(values)
            # if values[0] is None:
            #     result[key] = values[-1]
    return result

    for key, original_value in base_dict.items():
        if key in update_dict:
            if original_value is None:
                result[key] = update_dict[key]
            elif isinstance(original_value, list):
                result[key] = merge_schema_lists(original_value, update_dict[key], no_deletes)
            elif isinstance(original_value, dict):
                result[key] = merge_schema_dicts(original_value, update_dict[key], no_deletes)
            else:
                result[key] = update_dict[key]
        else:
            result[key] = original_value
    for key, update_value in update_dict.items():
        if key not in result:
            result[key] = update_value
    return result


def multi_merge(entity_lists: list[list[PartialEntity]]) -> list[Entity]:
    merged_dict_list = multi_merge_schema_lists([
        [
            entity.model_dump()
            if isinstance(entity, Entity) else
            entity.model_dump(exclude_defaults=True)
            for entity in entity_list
        ]
        for entity_list in entity_lists
    ])
    return [Entity(**x) for x in merged_dict_list]


def optimize_schema(entities: List[Entity]):
    entity_lookup = {entity.entity_name[0]: entity for entity in entities}
    attribute_tuples = [
        (entity, entity.entity_name[0], attribute, attribute.attribute_name[0])
        for entity in entities
        for attribute in entity.has_attribute
    ]

    # Apply certain patterns to improve detected content
    #  This probably also works like a reasoner (that also deletes the old stuff?!)
    # graph = build_graph(entities)
    # ero = Namespace(graph.namespace_manager.store.namespace('ero'))
    #
    # results = graph.query("""
    # SELECT ?entity ?entity_name ?attribute ?attribute_name
    # WHERE {
    #     ?entity a ero:Entity ;
    #             ero:entityName ?entity_name ;
    #             ero:hasAttribute ?attribute .
    #     ?attribute ero:attributeName ?attribute_name .
    # }
    # """)
    attribute_names_by_entity_name = collections.defaultdict(list)
    entity_names_by_attribute_name = collections.defaultdict(list)
    # for entity, entity_name, attribute, attribute_name in results:
    for entity, entity_name, attribute, attribute_name in attribute_tuples:
        attribute_names_by_entity_name[str(entity_name)].append(str(attribute_name))
        entity_names_by_attribute_name[str(attribute_name)].append(str(entity_name))

    # This strategy tries to find identical column names that end with _ID
    id_reference_lookup = {
        attribute_name: entity_list
        for attribute_name, entity_list in entity_names_by_attribute_name.items()
        if attribute_name.lower().endswith('_id')
        and attribute_name[:-3] in entity_list
    }
    for attribute_name, entity_list in id_reference_lookup.items():
        target_entity_name = attribute_name[:-3]
        # target_entity_url = entity_lookup[target_entity_name].entity_url
        for entity_name in entity_list:
            if entity_name != target_entity_name:
                source_entity = entity_lookup[entity_name]
                source_entity.is_subject_in_relation.append(
                    Relation(
                        relation_name=[str(attribute_name)],
                        has_object_entity=target_entity_name,
                        has_subject_entity=entity_name,
                        object_cardinality=create_cardinality((0, 1)),  # TODO could be 1,1 if we can check if attribute is optional or not
                        subject_cardinality=create_cardinality((0, sys.maxsize)),
                        has_attribute=[],
                        has_relation_modifier=None  # TODO could be identifying if we check, if the attribute is a key
                    )
                )
                attribute = [x for x in source_entity.has_attribute if x.attribute_name[0] == attribute_name][0]
                source_entity.has_attribute.remove(attribute)


    # # combined_attribute_names = set()
    # combined_name_lookup = collections.defaultdict(set)
    # for entity, entity_name, attribute, attribute_name in results:
    #     # print(entity_name, attribute_name)
    #     enl = entity_name.lower()
    #     anl = attribute_name.lower()
    #     new_combined_attribute_names = [
    #         f'{enl}{anl}',
    #         f'{enl}_{anl}',
    #         f'{enl}-{anl}',
    #         f'{enl}.{anl}'
    #     ]
    #     existing_combined_attribute_names = [
    #         x
    #         for x in new_combined_attribute_names
    #         if x in entity_names_by_attribute_name
    #     ]
    #     for combined_name in existing_combined_attribute_names:
    #         combined_name_lookup[combined_name].add((enl, anl))
    #
    #     # for new_attribute_name in new_combined_attribute_names:
    #     #     combined_attribute_names.add(new_attribute_name)
    #     #     combined_name_lookup[new_attribute_name]
    #
    # for combined_name, target_set in combined_name_lookup.items():
    #     _ = 42
    #
    # for entity, entity_name, attribute, attribute_name in results:
    #     anl = attribute_name.lower()
    #     if anl in combined_attribute_names:
    #         _ = 42  # TODO this could be another relation (or at least a suggestion for one)
    #         entity_name = str(entity_name)
    #         entity_object = [x for x in entities if x.entity_name[0] == entity_name][0]
    #         # attribute_object = [x for x in entity_object.has_attribute if x.attribute_name[0] == attribute_name][0]
    #         entity_object.is_subject_in_relation.append(
    #             Relation(
    #                 relation_name=[str(attribute_name)],
    #                 has_object_entity=fk_short_name,
    #                 has_subject_entity=short_name,
    #                 object_cardinality=create_cardinality((0, 1) if
    #                                                       foreign_key.nullable else (1, 1)),
    #                 subject_cardinality=subject_cardinality,
    #                 has_attribute=[],
    #                 has_relation_modifier=[RelationModifier(relation_modifier='identifying')]
    #                 if foreign_key in filtered_foreign_key_objects else None
    #             )
    #         )


    # results = graph.query("""
    # SELECT ?attribute ?value
    # WHERE {
    #     ?attribute a ero:Attribute ;
    #
    # }
    # """)


path_separator = '$'


def make_hierarchical_name(parent_name: str | None, child_name: str) -> str:
    if parent_name is None:
        parent_name = ''
    if len(parent_name) > 0 and not parent_name.startswith(path_separator):
        parent_name = f'{path_separator}{parent_name}'
    return f'{parent_name}{path_separator}{child_name}'


def split_prefix_and_item_name(path: str) -> Tuple[str, str]:
    if path_separator not in path:
        return '', path
    prefix, name = path.rsplit(path_separator, maxsplit=1)
    return prefix, name


def is_hierarchical_path(path: str) -> bool:
    if path.startswith(path_separator):
        return path_separator in path[1:]
    return path_separator in path


def convert_path_separator(path: str, new_separator: str) -> str:
    return path.replace(path_separator, new_separator)


class RenamingError(Exception):
    ...


class SchemaModdingContext:
    def __init__(self, storage: DataSourceStorage, schema_id: str):
        self.entities: list[PartialEntity] = []
        self.storage = storage
        self.schema_id = schema_id
        if schema_id not in storage.list_available_data():
            raise KeyError('schema not found')
        with storage.get_data(schema_id) as stream_lookup:
            if schema_correction_file_name in stream_lookup:
                self.entities = load_partial_schema_from_yaml(stream_lookup[schema_correction_file_name])
        self.modification_entities: list[PartialEntity] = []

    def _find_entity(self, current_active_name: str) -> PartialEntity | None:
        for entity in self.entities:
            if entity.entity_name[0] == current_active_name:
                return entity
        return None

    def _find_latest_entity(self, current_active_name: str) -> PartialEntity | None:
        entities = self._find_latest_entity_relatives(current_active_name)
        if entities:
            return entities[-1]
        return None

    def _find_entity_relatives(self, current_active_name: str) -> list[PartialEntity]:
        entities = [
            entity
            for entity in self.entities
            if current_active_name in entity.entity_name
        ]
        if entities:
            entities.sort(key=lambda x: len(x.entity_name))
        return entities

    def _find_latest_entity_relatives(self, current_active_name: str) -> list[PartialEntity]:
        entities = [
            entity
            for entity in self.entities
            if current_active_name == entity.entity_name[0]
        ]
        if entities:
            entities.sort(key=lambda x: len(x.entity_name))
        return entities

    def combine_and_persist(self):
        # entity_dict_list = [x.model_dump(exclude_defaults=True) for x in self.entities]
        # update_dict_list = [x.model_dump(exclude_defaults=True) for x in self.modification_entities]

        # A first attempt was using the deep_merge function from pydantic
        #  However, updating a dict will never properly work for the merging of entities with name overwrites
        #  as the names are not keys of the dict but stored in lists. The following implementation attempts to
        #  honor the name overwrite pattern accordingly

        # In the context of user corrections we switched to not combining the entities but keep a separate one for each
        #  user modification to better handle ordering of the individual operations
        # merged_dict_list = merge_schema_lists(entity_dict_list, update_dict_list, no_deletes=True)
        # result_entities = [PartialEntity(**x) for x in merged_dict_list]
        result_entities = self.entities + self.modification_entities
        yaml_string = serialize_partial_schema_to_yaml(result_entities)
        yaml_byte_stream = io.BytesIO(yaml_string.encode('utf-8'))
        self.storage.add_more_data(self.schema_id, {schema_correction_file_name: yaml_byte_stream})

    def rename_entity(self, current_entity_name: str, new_entity_name: str):
        if current_entity_name == new_entity_name:
            return
        existing_entity_correction = self._find_entity(current_entity_name)
        full_name_list = [new_entity_name, current_entity_name]
        if existing_entity_correction is not None:
            # raise ValueError('Entity not found')
            full_name_list = [new_entity_name, *existing_entity_correction.entity_name]
        self.modification_entities.append(PartialEntity(entity_name=full_name_list))

    @staticmethod
    def _find_attribute(attributes: list[PartialAttribute] | None, search_name: str) -> PartialAttribute | None:
        if attributes is None:
            return None
        for attribute in attributes:
            if attribute.attribute_name[0] == search_name:
                return attribute
        return None

    def rename_attribute(self, current_entity_name: str, current_attribute_name: str, new_attribute_name: str):
        if current_attribute_name == new_attribute_name:
            return
        existing_entity_correction = self._find_entity(current_entity_name)
        if existing_entity_correction is None:
            existing_entity_correction = PartialEntity(entity_name=[current_entity_name])
            self.modification_entities.append(existing_entity_correction)

        existing_attribute_correction = self._find_attribute(
            existing_entity_correction.has_attribute,
            current_attribute_name
        )
        if existing_attribute_correction is None:
            existing_attribute_correction = PartialAttribute(attribute_name=[current_attribute_name])
            if existing_entity_correction.has_attribute is None:
                existing_entity_correction.has_attribute = []
            existing_entity_correction.has_attribute.append(existing_attribute_correction)

        existing_attribute_correction.attribute_name = [
            new_attribute_name,
            *existing_attribute_correction.attribute_name
        ]

    @staticmethod
    def _find_relation(relations: list[PartialRelation] | None, search_name: str) -> PartialRelation | None:
        if relations is None:
            return None
        for relation in relations:
            if relation.relation_name[0] == search_name:
                return relation
        return None

    @staticmethod
    def _find_relation_relatives_from_entities(entities: list[PartialEntity], search_name: str) -> list[PartialRelation]:
        relations = []
        for entity in entities:
            if entity.is_subject_in_relation is not None:
                for relation in entity.is_subject_in_relation:
                    if search_name in relation.relation_name:
                        relations.append(relation)
        relations.sort(key=lambda x: len(x.relation_name))
        return relations

    def rename_relation(self, current_entity_name: str, current_relation_name: str, new_relation_name: str):
        if current_relation_name == new_relation_name:
            return

        existing_entity_corrections = self._find_entity_relatives(current_entity_name)
        if not existing_entity_corrections:
            existing_entity_correction = PartialEntity(entity_name=[current_entity_name])
            existing_entity_corrections = [existing_entity_correction]

        # existing_entity_correction = self._find_latest_entity(current_entity_name)
        # if existing_entity_correction is None:
        #     existing_entity_correction = PartialEntity(entity_name=[current_entity_name])
        #     self.modification_entities.append(existing_entity_correction)
        existing_relation_corrections = self._find_relation_relatives_from_entities(
            existing_entity_corrections,
            current_relation_name
        )
        if not existing_relation_corrections:
            existing_relation_corrections = [PartialRelation(relation_name=[current_relation_name])]

        latest_entity_name = existing_entity_corrections[-1].entity_name
        latest_relation_name = existing_relation_corrections[-1].relation_name

        self.modification_entities.append(PartialEntity(entity_name=latest_entity_name, is_subject_in_relation=[
            PartialRelation(relation_name=[
                new_relation_name,
                *latest_relation_name
            ])
        ]))

        # existing_relation_corrections = []
        # for entity in existing_entity_corrections:
        #     existing_relation_correction = self._find_relation(
        #         entity.is_subject_in_relation,
        #         current_relation_name
        #     )
        #     if existing_relation_correction is not None:
        #         existing_relation_corrections.append(existing_relation_correction)
        # if not existing_relation_corrections:
        #     existing_relation_corrections = [PartialRelation(relation_name=[current_relation_name])]

        # if existing_relation_correction is None:
        #     raise RenamingError()
        #     existing_relation_correction = PartialRelation(relation_name=[current_relation_name])
        #     if existing_entity_correction.is_subject_in_relation is None:
        #         existing_entity_correction.is_subject_in_relation = []
        #     existing_entity_correction.is_subject_in_relation.append(existing_relation_correction)

        # existing_relation_correction.relation_name = [
        #     new_relation_name,
        #     *existing_relation_correction.relation_name
        # ]
