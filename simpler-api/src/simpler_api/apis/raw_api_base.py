# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request



file = bytes


class BaseRawApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseRawApi.subclasses = BaseRawApi.subclasses + (cls,)
    def get_entity_raw_data(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        prevent_user_optimization: bool,
        generate_inverse_relations: bool,
    ) -> str:
        """desc"""
        ...
