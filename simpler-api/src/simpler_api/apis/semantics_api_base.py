# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request



file = bytes


class BaseSemanticsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSemanticsApi.subclasses = BaseSemanticsApi.subclasses + (cls,)
    def get_concept(
        self,
        request: Request,
        concept: str,
    ) -> str:
        """desc"""
        ...


    def get_jsonld_context(
        self,
        request: Request,
    ) -> str:
        """desc"""
        ...


    def get_ontology(
        self,
        request: Request,
    ) -> str:
        """desc"""
        ...
