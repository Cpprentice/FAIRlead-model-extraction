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
from simpler_api.models.class_definition_view import ClassDefinitionView
from simpler_api.models.model_schema import ModelSchema
from simpler_api.models.slot_definition_view import SlotDefinitionView


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)

file = bytes


@router.get(
    "/schemata",
    responses={
        200: {"model": List[ModelSchema], "description": "successful operation"},
    },
    tags=["schema"],
    summary="Get all available schemas from this API server",
    response_model_by_alias=True,
)
async def get_all_schemas(
    request: Request,
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> List[ModelSchema]:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_all_schemas(request, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations)


@router.get(
    "/schemata/{schemaId}/classes",
    responses={
        200: {"model": List[ClassDefinitionView], "description": "successful operation"},
    },
    tags=["schema"],
    summary="get all classes of a schema",
    response_model_by_alias=True,
)
async def get_classes_by_schema(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    prevent_structural_enhancement: bool = Query(False, description="", alias="preventStructuralEnhancement"),
    prevent_enhancement: bool = Query(False, description="", alias="preventEnhancement"),
    class_filter: List[str] = Query([], description="Only include classes of the schema that are in range of the specified classes", alias="classFilter"),
) -> List[ClassDefinitionView]:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_classes_by_schema(request, schemaId, prevent_structural_enhancement, prevent_enhancement, class_filter)


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
    schemaId: str = Path(..., description="ID of schema to access"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> ModelSchema:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_schema_by_id(request, schemaId, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations)


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
    schemaId: str = Path(..., description="ID of schema to access"),
    show_attributes: bool = Query(True, description="Toggle the rendering state of attributes", alias="showAttributes"),
    selected_entities: List[str] = Query([], description="Specify a list of highlighted entities", alias="selectedEntities"),
    render_distance: int = Query(2, description="The distance to render when using highlighted entities", alias="renderDistance"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> str:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_schema_diagram(request, schemaId, show_attributes, selected_entities, render_distance, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations)


@router.get(
    "/schemata/{schemaId}/classes/{classId}/slots",
    responses={
        200: {"model": List[SlotDefinitionView], "description": "successful operation"},
    },
    tags=["schema"],
    summary="get all slots of a class",
    response_model_by_alias=True,
)
async def get_slots_by_schema_and_class(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    classId: str = Path(..., description="ID of a class to access"),
    prevent_structural_enhancement: bool = Query(False, description="", alias="preventStructuralEnhancement"),
    prevent_enhancement: bool = Query(False, description="", alias="preventEnhancement"),
    class_filter: List[str] = Query([], description="Only include classes of the schema that are in range of the specified classes", alias="classFilter"),
) -> List[SlotDefinitionView]:
    """desc"""
    return BaseSchemaApi.subclasses[0]().get_slots_by_schema_and_class(request, schemaId, classId, prevent_structural_enhancement, prevent_enhancement, class_filter)
