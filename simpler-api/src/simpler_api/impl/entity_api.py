from typing import List
import urllib.parse

from fastapi import HTTPException, Request

from simpler_api.impl.plugins import get_cursor
from simpler_api.apis.entity_api_base import BaseEntityApi
from simpler_api.impl.schema_urls import introduce_api_urls_to_entity_list, introduce_api_urls_to_entity
from simpler_api.models.entity import Entity
from simpler_api.models.model_schema import ModelSchema
from simpler_core.plugin import InputDataError


class EntityApi(BaseEntityApi):
    def get_entities_by_schema(
        self,
        request: Request,
        schemaId: int,
        entity_prefix: str
    ) -> List[Entity]:

        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        try:
            entities = cursor.get_all_entities()
        except InputDataError as ex:
            raise HTTPException(status_code=400, detail="Schema extraction failed due to invalid input data") from ex

        introduce_api_urls_to_entity_list(entities, request, schemaId)
        return entities

    def get_entity_by_id(
        self,
        request: Request,
        schemaId: str,
        entityId: str
    ) -> Entity:
        try:
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail='Schema not found')

        try:
            entity = cursor.get_entity_by_id(entityId)
        except:
            raise HTTPException(status_code=404, detail="Entity not found")

        introduce_api_urls_to_entity(entity, request, schemaId)
        return entity
