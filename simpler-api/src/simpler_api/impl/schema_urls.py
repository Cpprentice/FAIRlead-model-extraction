from typing import List
import urllib.parse

from starlette.requests import Request

from simpler_model import Entity, Relation


def introduce_api_urls_to_entity_list(entities: List[Entity], request: Request, schema_id: str):
    for entity in entities:
        introduce_api_urls_to_entity(entity, request, schema_id)


def introduce_api_urls_to_entity(entity: Entity, request: Request, schema_id: str):
    if entity.is_subject_in_relation is not None:
        for relation in entity.is_subject_in_relation:
            introduce_api_urls_to_relation(relation, request, schema_id)
    if entity.is_object_in_relation is not None:
        for relation in entity.is_object_in_relation:
            introduce_api_urls_to_relation(relation, request, schema_id)


def introduce_api_urls_to_relation(relation: Relation, request: Request, schema_id: str):
    subject_path = urllib.parse.quote(relation.has_subject_entity, safe='')
    object_path = urllib.parse.quote(relation.has_object_entity, safe='')
    relation.has_subject_entity = f'{str(request.url_for(
        "get_entity_by_id",
        schemaId=schema_id,
        entityId=subject_path
    ))}'
    relation.has_object_entity = f'{str(request.url_for(
        "get_entity_by_id",
        schemaId=schema_id,
        entityId=object_path
    ))}'
