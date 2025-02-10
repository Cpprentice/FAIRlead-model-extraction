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

file = bytes


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
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
    entity_filter: List[str] = Query([], description="Only list entities of the schema that are in range of the specified entities", alias="entityFilter"),
    entity_filter_distance: int = Query(1, description="Specifies the search distance if entityFilter is used", alias="entityFilterDistance"),
) -> List[Entity]:
    """desc"""
    return BaseEntityApi.subclasses[0]().get_entities_by_schema(request, schemaId, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations, entity_filter, entity_filter_distance)


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
    entityId: str = Path(..., description="ID of entity to access"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> Entity:
    """desc"""
    return BaseEntityApi.subclasses[0]().get_entity_by_id(request, schemaId, entityId, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations)
