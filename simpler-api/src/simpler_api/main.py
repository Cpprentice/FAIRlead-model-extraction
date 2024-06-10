# coding: utf-8

"""
    Schema API - OpenAPI 3.0

    This is a Schema extraction API based on the OpenAPI 3.0 specification.  You can find out more about Swagger at [https://swagger.io](https://swagger.io). 

    The version of the OpenAPI document: 0.1.0
    Contact: philipp.schmurr@kit.edu
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


from fastapi import FastAPI

from simpler_api.apis.entity_api import router as EntityApiRouter
from simpler_api.apis.format_api import router as FormatApiRouter
from simpler_api.apis.schema_api import router as SchemaApiRouter

app = FastAPI(
    title="Schema API - OpenAPI 3.0",
    description="This is a Schema extraction API based on the OpenAPI 3.0 specification.  You can find out more about Swagger at [https://swagger.io](https://swagger.io). ",
    version="0.1.0",
)

app.include_router(EntityApiRouter)
app.include_router(FormatApiRouter)
app.include_router(SchemaApiRouter)
