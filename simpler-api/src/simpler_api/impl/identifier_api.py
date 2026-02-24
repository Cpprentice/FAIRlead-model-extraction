from fastapi import Request

from simpler_api.apis.identifier_api_base import BaseIdentifierApi
from simpler_api.impl.storage import get_id_storage


class IdentifierApi(BaseIdentifierApi):
    def schemata_schema_id_entities_entity_id_identifiers_post(
        self,
        request: Request,
        schemaId: str,
        entityId: str,
        body,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        prevent_user_optimization: bool,
        generate_inverse_relations: bool,
    ) -> str:
        storage = get_id_storage()
        return storage.get_id(body, schemaId, entityId)
