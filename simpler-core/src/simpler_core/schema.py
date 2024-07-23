import json
from typing import BinaryIO, List, TextIO

import yaml

from simpler_model import Entity


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


def serialize_entity_list_to_yaml(entities: List[Entity], target_stream: TextIO = None) -> str | None:
    dicts = [m.model_dump(exclude={'additional_properties'}) for m in entities]
    return yaml.safe_dump(dicts, target_stream)


def serialize_entity_list_to_json(entities: List[Entity], target_stream: TextIO = None) -> str | None:
    dicts = [m.model_dump(exclude={'additional_properties'}) for m in entities]
    if target_stream is None:
        return json.dumps(dicts, indent=4)
    json.dump(dicts, target_stream, indent=4)
