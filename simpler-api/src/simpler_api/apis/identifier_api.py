# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.identifier_api_base import BaseIdentifierApi
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


@router.post(
    "/schemata/{schemaId}/entities/{entityId}/identifiers",
    responses={
        200: {"model": str, "description": "successful operation"},
    },
    tags=["identifier"],
    summary="Get a unique ID - it is persisted if it did not exist yet",
    response_model_by_alias=True,
)
async def schemata_schema_id_entities_entity_id_identifiers_post(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    body = Body(None, description="Some local unique string (as json) that shall be used to find a consistent GUID"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> str:
    """desc"""
    return BaseIdentifierApi.subclasses[0]().schemata_schema_id_entities_entity_id_identifiers_post(request, schemaId, entityId, body, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations)
