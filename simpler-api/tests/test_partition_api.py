# coding: utf-8

from fastapi.testclient import TestClient


from simpler_api.models.partition import Partition  # noqa: F401


def test_get_partitioned_entities_by_schema(client: TestClient):
    """Test case for get_partitioned_entities_by_schema

    
    """
    params = [("prevent_optimization", False),     ("prevent_automatic_optimization", False),     ("generate_inverse_relations", False)]
    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/schemata/{schemaId}/partitioned-entities".format(schemaId='schema_id_example'),
    #    headers=headers,
    #    params=params,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

