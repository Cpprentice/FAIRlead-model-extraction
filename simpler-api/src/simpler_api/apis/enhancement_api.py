# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.enhancement_api_base import BaseEnhancementApi
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
from simpler_api.models.generic_enhancement_handler import GenericEnhancementHandler
from simpler_api.models.generic_enhancement_operation import GenericEnhancementOperation
from simpler_api.models.schema_enhancement import SchemaEnhancement


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)

file = bytes


@router.get(
    "/schemata/{schemaId}/enhancement",
    responses={
        200: {"model": SchemaEnhancement, "description": "Operation successful"},
        404: {"description": "Schema not found"},
    },
    tags=["enhancement"],
    summary="Get the current schema enhancement",
    response_model_by_alias=True,
)
async def get_schema_enhancement(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
) -> SchemaEnhancement:
    """Fetch all the enhancements of the specified schema"""
    return BaseEnhancementApi.subclasses[0]().get_schema_enhancement(request, schemaId)


@router.post(
    "/schemata/{schemaId}/enhancements/handlers",
    responses={
        200: {"description": "operation successful"},
        400: {"description": "bad request body"},
        404: {"description": "schema not found"},
    },
    tags=["enhancement"],
    summary="Insert a new enhancement handler",
    response_model_by_alias=True,
)
async def insert_enhancement_handler(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    generic_enhancement_handler: GenericEnhancementHandler = Body(None, description="The new handler"),
) -> None:
    """Append a new enhancement handler"""
    return BaseEnhancementApi.subclasses[0]().insert_enhancement_handler(request, schemaId, generic_enhancement_handler)


@router.post(
    "/schemata/{schemaId}/enhancement/operations",
    responses={
        200: {"description": "operation successful"},
        400: {"description": "bad request body"},
        404: {"description": "schema not found"},
    },
    tags=["enhancement"],
    summary="Insert a new enhancement operation",
    response_model_by_alias=True,
)
async def insert_enhancement_operation(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    generic_enhancement_operation: GenericEnhancementOperation = Body(None, description="The new operation"),
) -> None:
    """Append a new enhancement operation"""
    return BaseEnhancementApi.subclasses[0]().insert_enhancement_operation(request, schemaId, generic_enhancement_operation)


@router.put(
    "/schemata/{schemaId}/enhancement",
    responses={
        200: {"description": "Operation successful"},
        400: {"description": "Invalid data format"},
        404: {"description": "Schema not found"},
    },
    tags=["enhancement"],
    summary="Save the entire operations stack for this schema",
    response_model_by_alias=True,
)
async def set_schema_enhancement(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    schema_enhancement: SchemaEnhancement = Body(None, description="The entire state of configured schema enhancements"),
) -> None:
    """Overwrite the patches for the schema entirely"""
    return BaseEnhancementApi.subclasses[0]().set_schema_enhancement(request, schemaId, schema_enhancement)
