# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.semantics_api_base import BaseSemanticsApi
import simpler_api.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    Path,
    Query,
    Request,
    Response,
    Security,
    status,
)

from simpler_api.models.extra_models import TokenModel  # noqa: F401
from simpler_api.models.quantity import Quantity
from simpler_api.models.unit import Unit


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)

file = bytes


@router.get(
    "/semantics/ontology/{concept}",
    responses={
        200: {"model": str, "description": "successful operation"},
    },
    tags=["semantics"],
    summary="Get the ontology or the concept docs",
    response_model_by_alias=True,
)
async def get_concept(
    request: Request,
    concept: str = Path(..., description=""),
) -> str:
    """desc"""
    return BaseSemanticsApi.subclasses[0]().get_concept(request, concept)


@router.get(
    "/semantics/jsonld-context",
    responses={
        200: {"model": str, "description": "successful operation"},
    },
    tags=["semantics"],
    summary="Get the ERO ontology jsonld context",
    response_model_by_alias=True,
)
async def get_jsonld_context(
    request: Request,
) -> str:
    """desc"""
    return BaseSemanticsApi.subclasses[0]().get_jsonld_context(request, )


@router.get(
    "/semantics/ontology",
    responses={
        200: {"model": str, "description": "successful operation"},
    },
    tags=["semantics"],
    summary="Get the ERO ontology",
    response_model_by_alias=True,
)
async def get_ontology(
    request: Request,
) -> str:
    """desc"""
    return BaseSemanticsApi.subclasses[0]().get_ontology(request, )


@router.get(
    "/semantics/units",
    responses={
        200: {"model": List[Unit], "description": "Unit list"},
    },
    tags=["semantics"],
    summary="Get all QUDT SI Units",
    response_model_by_alias=True,
)
async def get_units(
    request: Request,
) -> List[Unit]:
    """Fetch all SI units"""
    return BaseSemanticsApi.subclasses[0]().get_units(request, )


@router.get(
    "/semantics/units/match",
    responses={
        200: {"model": Dict[str, str], "description": "Match lookup"},
    },
    tags=["semantics"],
    summary="Match a list of units against a list of texts",
    response_model_by_alias=True,
)
async def match_units(
    request: Request,
    unit_iris: List[str] = Query(None, description="", alias="unitIris"),
    unit_texts: List[str] = Query(None, description="", alias="unitTexts"),
) -> Dict[str, str]:
    """Find the best unit of a given set to a set of texts"""
    return BaseSemanticsApi.subclasses[0]().match_units(request, unit_iris, unit_texts)


@router.get(
    "/semantics/quantities/search",
    responses={
        200: {"model": List[Quantity], "description": "Top matches for search string"},
    },
    tags=["semantics"],
    summary="Search for QUDT quantity kinds that match a query",
    response_model_by_alias=True,
)
async def search_quantity_kinds(
    request: Request,
    search_string: List[str] = Query(None, description="", alias="searchString"),
    limit: int = Query(10, description="", alias="limit"),
) -> List[Quantity]:
    """Fetch quantity kinds based on a query string"""
    return BaseSemanticsApi.subclasses[0]().search_quantity_kinds(request, search_string, limit)


@router.get(
    "/semantics/units/search",
    responses={
        200: {"model": List[Unit], "description": "Top matches for search string"},
    },
    tags=["semantics"],
    summary="Search for QUDT units that match a query",
    response_model_by_alias=True,
)
async def search_units(
    request: Request,
    search_string: List[str] = Query(None, description="", alias="searchString"),
    limit: int = Query(10, description="", alias="limit"),
) -> List[Unit]:
    """Fetch units based on a query string"""
    return BaseSemanticsApi.subclasses[0]().search_units(request, search_string, limit)
