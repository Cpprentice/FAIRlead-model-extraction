# coding: utf-8

from fastapi.testclient import TestClient


from simpler_api.models.model_schema import ModelSchema  # noqa: F401


def test_get_all_schemas(client: TestClient):
    """Test case for get_all_schemas

    Get all avialable schemas from this API server
    """
    params = [("entity_prefix", '')]
    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/schemata",
    #    headers=headers,
    #    params=params,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_schema_by_id(client: TestClient):
    """Test case for get_schema_by_id

    Get schema by ID
    """
    params = [("entity_prefix", '')]
    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/schemata/{schemaId}".format(schemaId='schema_id_example'),
    #    headers=headers,
    #    params=params,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

