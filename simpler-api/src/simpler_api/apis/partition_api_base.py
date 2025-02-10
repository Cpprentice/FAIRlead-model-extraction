# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.partition import Partition


file = bytes


class BasePartitionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BasePartitionApi.subclasses = BasePartitionApi.subclasses + (cls,)
    def get_partitioned_entities_by_schema(
        self,
        request: Request,
        schemaId: str,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        prevent_user_optimization: bool,
        generate_inverse_relations: bool,
    ) -> List[Partition]:
        """desc"""
        ...
