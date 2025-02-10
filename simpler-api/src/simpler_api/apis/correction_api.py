# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.correction_api_base import BaseCorrectionApi
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
from simpler_api.models.attribute import Attribute
from simpler_api.models.attribute_modifier import AttributeModifier
from simpler_api.models.entity import Entity
from simpler_api.models.entity_modifier import EntityModifier
from simpler_api.models.relation import Relation
from simpler_api.models.relation_modifier import RelationModifier


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)

file = bytes


@router.post(
    "/schemata/{schemaId}/corrections/entities/{entityId}/attributes",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema or entity not found"},
    },
    tags=["correction"],
    summary="Add an entirely new attribute",
    response_model_by_alias=True,
)
async def add_new_attribute_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    attribute: Attribute = Body(None, description="A new attribute object"),
) -> None:
    """Add an entirely new attribute"""
    return BaseCorrectionApi.subclasses[0]().add_new_attribute_correction(request, schemaId, entityId, attribute)


@router.post(
    "/schemata/{schemaId}/corrections/entities",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema not found"},
    },
    tags=["correction"],
    summary="Add an entirely new entity",
    response_model_by_alias=True,
)
async def add_new_entity_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entity: Entity = Body(None, description="A new entity object"),
) -> None:
    """Add an entirely new entity"""
    return BaseCorrectionApi.subclasses[0]().add_new_entity_correction(request, schemaId, entity)


@router.post(
    "/schemata/{schemaId}/corrections/entities/{entityId}/relations",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema or entity not found"},
    },
    tags=["correction"],
    summary="Add an entirely new relation",
    response_model_by_alias=True,
)
async def add_new_relation_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    relation: Relation = Body(None, description="A new relation object"),
) -> None:
    """Add an entirely new relation"""
    return BaseCorrectionApi.subclasses[0]().add_new_relation_correction(request, schemaId, entityId, relation)


@router.post(
    "/schemata/{schemaId}/corrections/entities/{entityId}/attributes/{attributeId}",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema, entity or attribute not found"},
    },
    tags=["correction"],
    summary="change attribute name",
    response_model_by_alias=True,
)
async def change_attribute_name_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    attributeId: str = Path(..., description="ID of attribute to access"),
    body: str = Body(None, description="new name as plain string"),
) -> None:
    """change attribute name"""
    return BaseCorrectionApi.subclasses[0]().change_attribute_name_correction(request, schemaId, entityId, attributeId, body)


@router.post(
    "/schemata/{schemaId}/corrections/entities/{entityId}",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema or entity not found"},
    },
    tags=["correction"],
    summary="change entity name",
    response_model_by_alias=True,
)
async def change_entity_name_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    body: str = Body(None, description="new name as plain string"),
) -> None:
    """change entity name"""
    return BaseCorrectionApi.subclasses[0]().change_entity_name_correction(request, schemaId, entityId, body)


@router.post(
    "/schemata/{schemaId}/corrections/entities/{entityId}/relations/{relationId}",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema, entity or relation not found"},
    },
    tags=["correction"],
    summary="change relation name",
    response_model_by_alias=True,
)
async def change_relation_name_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    relationId: str = Path(..., description="ID of relation to access"),
    body: str = Body(None, description="new name as plain string"),
) -> None:
    """change relation name"""
    return BaseCorrectionApi.subclasses[0]().change_relation_name_correction(request, schemaId, entityId, relationId, body)


@router.put(
    "/schemata/{schemaId}/corrections/entities/{entityId}/attributes/{attributeId}/modifiers",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema, entity or attribute not found"},
    },
    tags=["correction"],
    summary="Update attribute modifiers",
    response_model_by_alias=True,
)
async def update_attribute_modifiers_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    attributeId: str = Path(..., description="ID of attribute to access"),
    attribute_modifier: List[AttributeModifier] = Body(None, description="list of AttributeModifier objects"),
) -> None:
    """Update attribute modifiers"""
    return BaseCorrectionApi.subclasses[0]().update_attribute_modifiers_correction(request, schemaId, entityId, attributeId, attribute_modifier)


@router.put(
    "/schemata/{schemaId}/corrections/entities/{entityId}/modifiers",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema or entity not found"},
    },
    tags=["correction"],
    summary="Update entity modifiers",
    response_model_by_alias=True,
)
async def update_entity_modifiers_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    entity_modifier: List[EntityModifier] = Body(None, description="list of EntityModifier objects"),
) -> None:
    """Update entity modifiers"""
    return BaseCorrectionApi.subclasses[0]().update_entity_modifiers_correction(request, schemaId, entityId, entity_modifier)


@router.put(
    "/schemata/{schemaId}/corrections/entities/{entityId}/relations/{relationId}/modifiers",
    responses={
        200: {"description": "successful operation"},
        400: {"model": str, "description": "bad request"},
        404: {"description": "schema, entity or relation not found"},
    },
    tags=["correction"],
    summary="Update relation modifiers",
    response_model_by_alias=True,
)
async def update_relation_modifiers_correction(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    entityId: str = Path(..., description="ID of entity to access"),
    relationId: str = Path(..., description="ID of relation to access"),
    relation_modifier: List[RelationModifier] = Body(None, description="list of RelationModifier objects"),
) -> None:
    """Update relation modifiers"""
    return BaseCorrectionApi.subclasses[0]().update_relation_modifiers_correction(request, schemaId, entityId, relationId, relation_modifier)
