# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.generic_enhancement_handler import GenericEnhancementHandler
from simpler_api.models.generic_enhancement_operation import GenericEnhancementOperation
from simpler_api.models.schema_enhancement import SchemaEnhancement


file = bytes


class BaseEnhancementApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseEnhancementApi.subclasses = BaseEnhancementApi.subclasses + (cls,)
    def get_schema_enhancement(
        self,
        request: Request,
        schemaId: str,
    ) -> SchemaEnhancement:
        """Fetch all the enhancements of the specified schema"""
        ...


    def insert_enhancement_handler(
        self,
        request: Request,
        schemaId: str,
        generic_enhancement_handler: GenericEnhancementHandler,
    ) -> None:
        """Append a new enhancement handler"""
        ...


    def insert_enhancement_operation(
        self,
        request: Request,
        schemaId: str,
        generic_enhancement_operation: GenericEnhancementOperation,
    ) -> None:
        """Append a new enhancement operation"""
        ...


    def set_schema_enhancement(
        self,
        request: Request,
        schemaId: str,
        schema_enhancement: SchemaEnhancement,
    ) -> None:
        """Overwrite the patches for the schema entirely"""
        ...
