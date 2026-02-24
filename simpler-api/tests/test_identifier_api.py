# coding: utf-8

from fastapi.testclient import TestClient




def test_schemata_schema_id_entities_entity_id_identifiers_post(client: TestClient):
    """Test case for schemata_schema_id_entities_entity_id_identifiers_post

    Get a unique ID - it is persisted if it did not exist yet
    """
    body = 'body_example'
    params = [("prevent_optimization", False),     ("prevent_automatic_optimization", False),     ("prevent_user_optimization", False),     ("generate_inverse_relations", False)]
    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/schemata/{schemaId}/entities/{entityId}/identifiers".format(schemaId='schema_id_example', entityId='entity_id_example'),
    #    headers=headers,
    #    json=body,
    #    params=params,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

