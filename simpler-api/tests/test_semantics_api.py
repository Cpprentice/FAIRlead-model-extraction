# coding: utf-8

from fastapi.testclient import TestClient




def test_get_jsonld_context(client: TestClient):
    """Test case for get_jsonld_context

    Get the ERO ontology jsonld context
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/semantics/jsonld-context",
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_ontology(client: TestClient):
    """Test case for get_ontology

    Get the ERO ontology
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/semantics/ontology",
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

