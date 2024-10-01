# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.schema_api_base import BaseSchemaApi
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
from simpler_api.models.model_schema import ModelSchema


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/schemata",
    responses={
        200: {"model": List[ModelSchema], "description": "successful operation"},
    },
    tags=["schema"],
    summary="Get all avialable schemas from this API server",
    response_model_by_alias=True,
)
async def get_all_schemas(
    request: Request,
) -> List[ModelSchema]:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_all_schemas(request, )


@router.get(
    "/schemata/{schemaId}",
    responses={
        200: {"model": ModelSchema, "description": "successful operation"},
        404: {"description": "not found"},
    },
    tags=["schema"],
    summary="Get schema by ID",
    response_model_by_alias=True,
)
async def get_schema_by_id(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to return"),
) -> ModelSchema:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_schema_by_id(request, schemaId)


@router.get(
    "/schemata/{schemaId}/diagram",
    responses={
        200: {"model": str, "description": "successful operation"},
        404: {"description": "schema not found"},
    },
    tags=["schema"],
    summary="Get a diagram for the schema",
    response_model_by_alias=True,
)
async def get_schema_diagram(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to return"),
    show_attributes: bool = Query(True, description="Toggle the rendering state of attributes", alias="showAttributes"),
    selected_entities: List[str] = Query([], description="Specify a list of highlighted entities", alias="selectedEntities"),
    render_distance: int = Query(2, description="The distance to render when using highlighted entities", alias="renderDistance"),
    generate_inverse_relations: bool = Query(True, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> str:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_schema_diagram(request, schemaId, show_attributes, selected_entities, render_distance, generate_inverse_relations)
