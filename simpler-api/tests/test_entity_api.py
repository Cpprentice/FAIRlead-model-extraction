# coding: utf-8

from fastapi.testclient import TestClient


from simpler_api.models.entity import Entity  # noqa: F401


def test_get_entities_by_schema(client: TestClient):
    """Test case for get_entities_by_schema

    Get all entities of a schema
    """
    params = [("entity_prefix", '')]
    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/schemata/{schemaId}/entities".format(schemaId='schema_id_example'),
    #    headers=headers,
    #    params=params,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_entity_by_id(client: TestClient):
    """Test case for get_entity_by_id

    Get a specific entity
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/schemata/{schemaId}/entities/{entityId}".format(schemaId='schema_id_example', entityId='entity_id_example'),
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

