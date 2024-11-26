# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.entity_api_base import BaseEntityApi
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
from simpler_api.models.entity import Entity


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/schemata/{schemaId}/entities",
    responses={
        200: {"model": List[Entity], "description": "successful operation"},
    },
    tags=["entity"],
    summary="Get all entities of a schema",
    response_model_by_alias=True,
)
async def get_entities_by_schema(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> List[Entity]:
    """desc"""
    return BaseEntityApi.subclasses[0]().get_entities_by_schema(request, schemaId, prevent_optimization, prevent_automatic_optimization, generate_inverse_relations)


@router.get(
    "/schemata/{schemaId}/entities/{entityId}",
    responses={
        200: {"model": Entity, "description": "successful operation"},
    },
    tags=["entity"],
    summary="Get a specific entity",
    response_model_by_alias=True,
)
async def get_entity_by_id(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to return"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> Entity:
    """desc"""
    return BaseEntityApi.subclasses[0]().get_entity_by_id(request, schemaId, entityId, prevent_optimization, prevent_automatic_optimization, generate_inverse_relations)
