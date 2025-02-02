# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.data_source_api_base import BaseDataSourceApi
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
from simpler_api.models.data_source import DataSource


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)

file = bytes


@router.post(
    "/data-sources",
    responses={
        200: {"model": DataSource, "description": "successful operation"},
        400: {"description": "Bad request"},
    },
    tags=["data-source"],
    summary="Insert a new data source meta record",
    response_model_by_alias=True,
)
async def add_data_source_meta(
    request: Request,
    data_source: DataSource = Body(None, description="specification of data source meta record"),
) -> DataSource:
    """desc"""
    return BaseDataSourceApi.subclasses[0]().add_data_source_meta(request, data_source)


@router.get(
    "/data-sources",
    responses={
        200: {"model": List[DataSource], "description": "successful operation"},
    },
    tags=["data-source"],
    summary="Get meta information about all registered data sources",
    response_model_by_alias=True,
)
async def get_all_data_source_meta(
    request: Request,
) -> List[DataSource]:
    """desc"""
    return BaseDataSourceApi.subclasses[0]().get_all_data_source_meta(request, )


@router.get(
    "/data-sources/{dataSourceId}/{pluginInputField}",
    responses={
        200: {"model": file, "description": "successful operation"},
    },
    tags=["data-source"],
    summary="Get content of a specified data sources",
    response_model_by_alias=True,
)
async def get_data_source_content(
    request: Request,
    dataSourceId: str = Path(..., description=""),
    pluginInputField: str = Path(..., description=""),
) -> file:
    """desc"""
    return BaseDataSourceApi.subclasses[0]().get_data_source_content(request, dataSourceId, pluginInputField)


@router.get(
    "/data-sources/{dataSourceId}",
    responses={
        200: {"model": List[DataSource], "description": "successful operation"},
    },
    tags=["data-source"],
    summary="Get meta information about a specified data sources",
    response_model_by_alias=True,
)
async def get_data_source_meta(
    request: Request,
    dataSourceId: str = Path(..., description=""),
) -> List[DataSource]:
    """desc"""
    return BaseDataSourceApi.subclasses[0]().get_data_source_meta(request, dataSourceId)


@router.post(
    "/data-sources/{dataSourceId}/{pluginInputField}",
    responses={
        200: {"description": "successful operation"},
    },
    tags=["data-source"],
    summary="Upload the content of a specified data source",
    response_model_by_alias=True,
)
async def upload_data_source_content(
    request: Request,
    dataSourceId: str = Path(..., description=""),
    pluginInputField: str = Path(..., description=""),
) -> None:
    """desc"""
    return BaseDataSourceApi.subclasses[0]().upload_data_source_content(request, dataSourceId, pluginInputField)
