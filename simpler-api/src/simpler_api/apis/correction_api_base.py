# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.attribute import Attribute
from simpler_api.models.attribute_modifier import AttributeModifier
from simpler_api.models.entity import Entity
from simpler_api.models.entity_modifier import EntityModifier
from simpler_api.models.relation import Relation
from simpler_api.models.relation_modifier import RelationModifier


file = bytes


class BaseCorrectionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseCorrectionApi.subclasses = BaseCorrectionApi.subclasses + (cls,)
    def add_new_attribute_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        attribute: Attribute,
    ) -> None:
        """Add an entirely new attribute"""
        ...


    def add_new_entity_correction(
        self,
        request: Request,
        schemaId: str,
        entity: Entity,
    ) -> None:
        """Add an entirely new entity"""
        ...


    def add_new_relation_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        relation: Relation,
    ) -> None:
        """Add an entirely new relation"""
        ...


    def change_attribute_name_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        attributeId: str,
        body: str,
    ) -> None:
        """change attribute name"""
        ...


    def change_entity_name_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        body: str,
    ) -> None:
        """change entity name"""
        ...


    def change_relation_name_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        relationId: str,
        body: str,
    ) -> None:
        """change relation name"""
        ...


    def update_attribute_modifiers_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        attributeId: str,
        attribute_modifier: List[AttributeModifier],
    ) -> None:
        """Update attribute modifiers"""
        ...


    def update_entity_modifiers_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        entity_modifier: List[EntityModifier],
    ) -> None:
        """Update entity modifiers"""
        ...


    def update_relation_modifiers_correction(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        relationId: str,
        relation_modifier: List[RelationModifier],
    ) -> None:
        """Update relation modifiers"""
        ...
