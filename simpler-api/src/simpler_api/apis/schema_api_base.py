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
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        generate_inverse_relations: bool,
    ) -> List[ModelSchema]:
        """desc"""
        ...


    def get_schema_by_id(
        self,
        request: Request,
        schemaId: str,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        generate_inverse_relations: bool,
    ) -> ModelSchema:
        """desc"""
        ...


    def get_schema_diagram(
        self,
        request: Request,
        schemaId: str,
        show_attributes: bool,
        selected_entities: List[str],
        render_distance: int,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        generate_inverse_relations: bool,
    ) -> str:
        """desc"""
        ...
