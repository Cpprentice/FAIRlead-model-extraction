# coding: utf-8

from fastapi.testclient import TestClient


from simpler_api.models.data_source import DataSource  # noqa: F401


def test_add_data_source_meta(client: TestClient):
    """Test case for add_data_source_meta

    Insert a new data source meta record
    """
    data_source = {"plugin":"plugin","description":"description","id":"id","text_data":[{"input_field":"input_field","value":"value"},{"input_field":"input_field","value":"value"}],"populated_input_fields":["populated_input_fields","populated_input_fields"]}

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/data-sources",
    #    headers=headers,
    #    json=data_source,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_all_data_source_meta(client: TestClient):
    """Test case for get_all_data_source_meta

    Get meta information about all registered data sources
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/data-sources",
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_data_source_content(client: TestClient):
    """Test case for get_data_source_content

    Get content of a specified data sources
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/data-sources/{dataSourceId}/{pluginInputField}".format(dataSourceId='data_source_id_example', pluginInputField='plugin_input_field_example'),
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_data_source_meta(client: TestClient):
    """Test case for get_data_source_meta

    Get meta information about a specified data sources
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/data-sources/{dataSourceId}".format(dataSourceId='data_source_id_example'),
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_upload_data_source_content(client: TestClient):
    """Test case for upload_data_source_content

    Upload the content of a specified data source
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/data-sources/{dataSourceId}/{pluginInputField}".format(dataSourceId='data_source_id_example', pluginInputField='plugin_input_field_example'),
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

