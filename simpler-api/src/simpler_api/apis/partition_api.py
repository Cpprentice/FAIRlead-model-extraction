# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.partition_api_base import BasePartitionApi
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
from simpler_api.models.partition import Partition


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)

file = bytes


@router.get(
    "/schemata/{schemaId}/partitioned-entities",
    responses={
        200: {"model": List[Partition], "description": "successful operation"},
    },
    tags=["partition"],
    response_model_by_alias=True,
)
async def get_partitioned_entities_by_schema(
    request: Request,
    schemaId: str = Path(..., description="ID of schema to access"),
    prevent_optimization: bool = Query(False, description="", alias="preventOptimization"),
    prevent_automatic_optimization: bool = Query(False, description="", alias="preventAutomaticOptimization"),
    prevent_user_optimization: bool = Query(False, description="", alias="preventUserOptimization"),
    generate_inverse_relations: bool = Query(False, description="Toggles whether to generate inverse relations for each existing relation that has no schema based inverse", alias="generateInverseRelations"),
) -> List[Partition]:
    """desc"""
    return BasePartitionApi.subclasses[0]().get_partitioned_entities_by_schema(request, schemaId, prevent_optimization, prevent_automatic_optimization, prevent_user_optimization, generate_inverse_relations)
