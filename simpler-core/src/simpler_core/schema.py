import collections
import json
from contextlib import suppress
from types import NoneType
from typing import BinaryIO, List, TextIO, Tuple, Sequence, get_origin, get_args, Any, Dict

import yaml
from pydantic import BaseModel, BaseConfig, PydanticUndefinedAnnotation, create_model
from pydantic.v1.utils import deep_update
from pydantic_core.core_schema import ModelField
from pydantic_partial import create_partial_model
from pydantic_partial._compat import PydanticCompat

from simpler_model import Entity
try:
    from simpler_model import Relation
    EntityLink = Relation
except ImportError:
    from simpler_model import EntityLink
    Relation = EntityLink


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
    'PartialRelation': ['relation_name']
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

        with suppress(PydanticUndefinedAnnotation):
            cls.model_rebuild(force=True)


def make_optional(base_class: type[BaseModel]) -> type:
    return create_model(f'Partial{base_class.__name__}', __base__=(base_class, OptionalModel))


class PartialEntity(Entity, OptionalModel):
    pass


# class PartialRelation(Relation, OptionalModel):
#     pass

PartialRelation = make_optional(Relation)


# PartialEntity = create_partial_model(Entity, recursive=True)
# PartialRelation = create_partial_model(Relation, recursive=True)

replacements = {
    Relation: PartialRelation
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


def extend_schema_from_yaml(entities: List[Entity], binary_stream: BinaryIO) -> List[Entity]:
    entity_extension_data_list = yaml.safe_load(binary_stream)
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
    result_entities = [Entity(**x) for x in merged_dict_list]
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


def merge_schema_lists(base_list: List, update_list: List) -> List:
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
        while len(items) > 1:
            base = items[0]
            update = items[1]
            result = merge_schema_dicts(base, update)
            items = [result, *items[2:]]
        result_list.append(items[0])
    return result_list


def merge_schema_dicts(base_dict: Dict, update_dict: Dict) -> Dict:
    result = {}
    for key, original_value in base_dict.items():
        if key in update_dict:
            if original_value is None:
                result[key] = update_dict[key]
            elif isinstance(original_value, list):
                result[key] = merge_schema_lists(original_value, update_dict[key])
            elif isinstance(original_value, dict):
                result[key] = merge_schema_dicts(original_value, update_dict[key])
            else:
                result[key] = update_dict[key]
        else:
            result[key] = original_value
    for key, update_value in update_dict.items():
        if key not in result:
            result[key] = update_value
    return result


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
