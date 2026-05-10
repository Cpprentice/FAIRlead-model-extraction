
from fastapi import Request, HTTPException

from fairlead_core.patching import convert_generic_operation_to_actual_operation
from fairlead_core.plugin import InputDataError
from fairlead_core.schema import load_schema_enhancement, add_enhancement_operation, add_enhancement_handler
from simpler_api.apis.enhancement_api_base import BaseEnhancementApi
from simpler_api.impl.plugins import get_cursor
from simpler_api.impl.response import wrap_response_according_to_accept_header
from simpler_model import SchemaEnhancement, EnhancementOperation, GenericEnhancementOperation, \
    GenericEnhancementHandler


class EnhancementApi(BaseEnhancementApi):
    def get_schema_enhancement(
            self,
            request: Request,
            schemaId: str,
    ) -> SchemaEnhancement:
        """Fetch all the enhancements of the specified schema"""
        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        schema_enhancement = load_schema_enhancement(cursor.plugin.storage, schemaId)

        return wrap_response_according_to_accept_header(request, schema_enhancement)

    def insert_enhancement_operation(
            self,
            request: Request,
            schemaId: str,
            generic_enhancement_operation: GenericEnhancementOperation,
    ) -> None:
        """Append a new enhancement operation"""
        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        try:
            # actual_operation = convert_generic_operation_to_actual_operation(generic_enhancement_operation)
            add_enhancement_operation(cursor.plugin.storage, schemaId, generic_enhancement_operation)
        except:
            raise HTTPException(status_code=400, detail="Actual operation can not be built from body")


    def insert_enhancement_handler(
        self,
        request: Request,
        schemaId: str,
        generic_enhancement_handler: GenericEnhancementHandler,
    ) -> None:
        """Append a new enhancement handler"""
        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        try:
            # actual_operation = convert_generic_operation_to_actual_operation(generic_enhancement_operation)
            add_enhancement_handler(cursor.plugin.storage, schemaId, generic_enhancement_handler)
        except:
            raise HTTPException(status_code=400, detail="Actual operation can not be built from body")


    def set_schema_enhancement(
            self,
            request: Request,
            schemaId: str,
            schema_enhancement: SchemaEnhancement,
    ) -> None:
        """Overwrite the patches for the schema entirely"""
        ...
