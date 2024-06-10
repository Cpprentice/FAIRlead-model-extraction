# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.model_schema import ModelSchema


class BaseSchemaApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSchemaApi.subclasses = BaseSchemaApi.subclasses + (cls,)
    def get_all_schemas(
        self,
        request: Request,
        entity_prefix: str,
    ) -> List[ModelSchema]:
        """desc"""
        ...


    def get_schema_by_id(
        self,
        request: Request,
        schemaId: str,
        entity_prefix: str,
    ) -> ModelSchema:
        """desc"""
        ...


    def get_schema_diagram(
        self,
        request: Request,
        schemaId: str,
        show_attributes: bool,
    ) -> str:
        """desc"""
        ...
