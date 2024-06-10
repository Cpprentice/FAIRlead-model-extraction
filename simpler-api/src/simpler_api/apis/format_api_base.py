# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.format import Format


class BaseFormatApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseFormatApi.subclasses = BaseFormatApi.subclasses + (cls,)
    def get_all_formats(
        self,
        request: Request,
    ) -> List[Format]:
        """desc"""
        ...
