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
