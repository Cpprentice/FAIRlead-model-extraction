# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.entity import Entity


class BaseEntityApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseEntityApi.subclasses = BaseEntityApi.subclasses + (cls,)
    def get_entities_by_schema(
        self,
        request: Request,
        schemaId: str,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        generate_inverse_relations: bool,
    ) -> List[Entity]:
        """desc"""
        ...


    def get_entity_by_id(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        generate_inverse_relations: bool,
    ) -> Entity:
        """desc"""
        ...
