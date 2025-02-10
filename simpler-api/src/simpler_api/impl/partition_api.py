from typing import List

from fastapi import Request, HTTPException

from simpler_api.apis.partition_api_base import BasePartitionApi
from simpler_api.impl.plugins import get_cursor
from simpler_api.impl.response import wrap_response_according_to_accept_header
from simpler_api.impl.schema_urls import introduce_api_urls_to_entity_list
from simpler_core.partitioning import create_partitioned_entity_list
from simpler_core.plugin import InputDataError
from simpler_model import Partition


class PartitionApi(BasePartitionApi):
    def get_partitioned_entities_by_schema(
        self,
        request: Request,
        schemaId: str,
        prevent_optimization: bool,
        prevent_automatic_optimization: bool,
        prevent_user_optimization: bool,
        generate_inverse_relations: bool,
    ) -> List[Partition]:
        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schemaId)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")

        try:
            entities = cursor.get_all_entities()
        except InputDataError as ex:
            raise HTTPException(status_code=400, detail="Schema extraction failed due to invalid input data") from ex

        partitions = create_partitioned_entity_list(entities)
        for partition in partitions:
            introduce_api_urls_to_entity_list(partition.entities, request, schemaId)

        return wrap_response_according_to_accept_header(request, partitions)
