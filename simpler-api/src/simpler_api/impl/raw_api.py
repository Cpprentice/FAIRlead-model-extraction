from fastapi import Request, Response, HTTPException

from simpler_api.apis.raw_api_base import BaseRawApi
from simpler_api.impl.plugins import get_cursor
from simpler_api.impl.schema_urls import introduce_api_urls_to_entity


class RawApi(BaseRawApi):

    def get_entity_raw_data(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        prevent_user_optimization: bool,
        generate_inverse_relations: bool,
    ) -> str:
        try:
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail='Schema not found')

        try:
            raw_data, mime_type = cursor.get_raw_data_by_entity(entityId)
            return Response(raw_data, media_type=mime_type)
        except:
            raise HTTPException(status_code=404, detail="Entity not found")
