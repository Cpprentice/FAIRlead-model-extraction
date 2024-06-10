# coding: utf-8

from fastapi.testclient import TestClient


from simpler_api.models.format import Format  # noqa: F401


def test_get_all_formats(client: TestClient):
    """Test case for get_all_formats

    Get all supported formats of this API
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/formats",
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

