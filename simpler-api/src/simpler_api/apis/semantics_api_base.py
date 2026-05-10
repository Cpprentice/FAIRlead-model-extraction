# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.quantity import Quantity
from simpler_api.models.unit import Unit


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


    def get_units(
        self,
        request: Request,
    ) -> List[Unit]:
        """Fetch all SI units"""
        ...


    def match_units(
        self,
        request: Request,
        unit_iris: List[str],
        unit_texts: List[str],
    ) -> Dict[str, str]:
        """Find the best unit of a given set to a set of texts"""
        ...


    def search_quantity_kinds(
        self,
        request: Request,
        search_string: List[str],
        limit: int,
    ) -> List[Quantity]:
        """Fetch quantity kinds based on a query string"""
        ...


    def search_units(
        self,
        request: Request,
        search_string: List[str],
        limit: int,
    ) -> List[Unit]:
        """Fetch units based on a query string"""
        ...
