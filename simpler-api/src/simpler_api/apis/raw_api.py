# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.raw_api_base import BaseRawApi
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
    "/schemata/{schemaId}/entities/{entityId}/raw",
    responses={
        200: {"model": str, "description": "successful operation"},
    },
    tags=["raw"],
    summary="Get a raw data set of that entity",
    response_model_by_alias=True,
)
async def get_entity_raw_data(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> str:
    """desc"""
    return BaseRawApi.subclasses[0]().get_entity_raw_data(request, schemaId, entityId, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations)
