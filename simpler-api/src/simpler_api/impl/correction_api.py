from typing import List

from fastapi import Request, HTTPException

from simpler_api.apis.correction_api_base import BaseCorrectionApi
from simpler_api.impl.storage import get_storage
from fairlead_core.schema import SchemaModdingContext
from simpler_model import Attribute, Entity, Relation, AttributeModifier, EntityModifier, RelationModifier


class CorrectionApi(BaseCorrectionApi):
    def add_new_attribute_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        attribute: Attribute,
    ) -> None:
        ...


    def add_new_entity_correction(
        self,
        request: Request,
        schemaId: str,
        entity: Entity,
    ) -> None:
        ...


    def add_new_relation_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        relation: Relation,
    ) -> None:
        ...


    def change_attribute_name_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        attributeId: str,
        body: str,
    ) -> None:
        storage = get_storage()
        try:
            context = SchemaModdingContext(storage, schemaId)
            context.rename_attribute(entityId, attributeId, body)
        except KeyError as ex:
            raise HTTPException(status_code=404, detail='Schema not found') from ex
        except ValueError as ex:
            raise HTTPException(status_code=404) from ex

        context.combine_and_persist()

    def change_entity_name_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        body: str,
    ) -> None:
        storage = get_storage()
        try:
            context = SchemaModdingContext(storage, schemaId)
            context.rename_entity(entityId, body)
        except KeyError as ex:
            raise HTTPException(status_code=404, detail='Schema not found') from ex
        except ValueError as ex:
            raise HTTPException(status_code=404) from ex

        context.combine_and_persist()

    def change_relation_name_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        relationId: str,
        body: str,
    ) -> None:
        storage = get_storage()
        try:
            context = SchemaModdingContext(storage, schemaId)
            context.rename_relation(entityId, relationId, body)
        except KeyError as ex:
            raise HTTPException(status_code=404, detail='Schema not found') from ex
        except ValueError as ex:
            raise HTTPException(status_code=404) from ex

        context.combine_and_persist()


    def update_attribute_modifiers_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        attributeId: str,
        attribute_modifier: List[AttributeModifier],
    ) -> None:
        ...


    def update_entity_modifiers_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        entity_modifier: List[EntityModifier],
    ) -> None:
        ...


    def update_relation_modifiers_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        relationId: str,
        relation_modifier: List[RelationModifier],
    ) -> None:
        ...
