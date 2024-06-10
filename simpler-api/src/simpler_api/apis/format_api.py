# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from simpler_api.apis.format_api_base import BaseFormatApi
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
from simpler_api.models.format import Format


router = APIRouter()

ns_pkg = simpler_api.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/formats",
    responses={
        200: {"model": List[Format], "description": "successful operation"},
    },
    tags=["format"],
    summary="Get all supported formats of this API",
    response_model_by_alias=True,
)
async def get_all_formats(
    request: Request,
) -> List[Format]:
    """desc"""
    return BaseFormatApi.subclasses[0]().get_all_formats(request, )
