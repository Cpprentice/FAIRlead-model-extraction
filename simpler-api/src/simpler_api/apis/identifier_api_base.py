# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request



file = bytes


class BaseIdentifierApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseIdentifierApi.subclasses = BaseIdentifierApi.subclasses + (cls,)
    def schemata_schema_id_entities_entity_id_identifiers_post(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        body,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        prevent_user_optimization: bool,
        generate_inverse_relations: bool,
    ) -> str:
        """desc"""
        ...
