# coding: utf-8

from fastapi.testclient import TestClient




def test_get_entity_raw_data(client: TestClient):
    """Test case for get_entity_raw_data

    Get a raw data set of that entity
    """
    params = [("prevent_optimization", False),     ("prevent_automatic_optimization", False),     ("prevent_user_optimization", False),     ("generate_inverse_relations", False)]
    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/schemata/{schemaId}/entities/{entityId}/raw".format(schemaId='schema_id_example', entityId='entity_id_example'),
    #    headers=headers,
    #    params=params,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

