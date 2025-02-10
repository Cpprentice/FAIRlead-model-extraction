# coding: utf-8

from fastapi.testclient import TestClient


from simpler_api.models.attribute import Attribute  # noqa: F401
from simpler_api.models.attribute_modifier import AttributeModifier  # noqa: F401
from simpler_api.models.entity import Entity  # noqa: F401
from simpler_api.models.entity_modifier import EntityModifier  # noqa: F401
from simpler_api.models.relation import Relation  # noqa: F401
from simpler_api.models.relation_modifier import RelationModifier  # noqa: F401


def test_add_new_attribute_correction(client: TestClient):
    """Test case for add_new_attribute_correction

    Add an entirely new attribute
    """
    attribute = {"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]}

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}/attributes".format(schemaId='schema_id_example', entityId='entity_id_example'),
    #    headers=headers,
    #    json=attribute,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_add_new_entity_correction(client: TestClient):
    """Test case for add_new_entity_correction

    Add an entirely new entity
    """
    entity = {"is_object_in_relation":[{"object_cardinality":{"cardinality":"cardinality"},"subject_cardinality":{"cardinality":"cardinality"},"has_subject_entity":"","relation_name":["relationName","relationName"],"has_object_entity":"","inverse_relation":"inverseRelation","has_attribute":[{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]},{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]}],"has_relation_modifier":[{"relation_modifier":"relationModifier"},{"relation_modifier":"relationModifier"}]},{"object_cardinality":{"cardinality":"cardinality"},"subject_cardinality":{"cardinality":"cardinality"},"has_subject_entity":"","relation_name":["relationName","relationName"],"has_object_entity":"","inverse_relation":"inverseRelation","has_attribute":[{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]},{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]}],"has_relation_modifier":[{"relation_modifier":"relationModifier"},{"relation_modifier":"relationModifier"}]}],"has_entity_modifier":[{"entity_modifier":"entityModifier"},{"entity_modifier":"entityModifier"}],"entity_name":["entityName","entityName"],"entity_url":"entityUrl","has_attribute":[{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]},{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]}],"is_subject_in_relation":[{"object_cardinality":{"cardinality":"cardinality"},"subject_cardinality":{"cardinality":"cardinality"},"has_subject_entity":"","relation_name":["relationName","relationName"],"has_object_entity":"","inverse_relation":"inverseRelation","has_attribute":[{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]},{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]}],"has_relation_modifier":[{"relation_modifier":"relationModifier"},{"relation_modifier":"relationModifier"}]},{"object_cardinality":{"cardinality":"cardinality"},"subject_cardinality":{"cardinality":"cardinality"},"has_subject_entity":"","relation_name":["relationName","relationName"],"has_object_entity":"","inverse_relation":"inverseRelation","has_attribute":[{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]},{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]}],"has_relation_modifier":[{"relation_modifier":"relationModifier"},{"relation_modifier":"relationModifier"}]}]}

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/schemata/{schemaId}/corrections/entities".format(schemaId='schema_id_example'),
    #    headers=headers,
    #    json=entity,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_add_new_relation_correction(client: TestClient):
    """Test case for add_new_relation_correction

    Add an entirely new relation
    """
    relation = {"object_cardinality":{"cardinality":"cardinality"},"subject_cardinality":{"cardinality":"cardinality"},"has_subject_entity":"","relation_name":["relationName","relationName"],"has_object_entity":"","inverse_relation":"inverseRelation","has_attribute":[{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]},{"attribute_name":["attributeName","attributeName"],"has_attribute_modifier":[{"attribute_modifier":"attributeModifier"},{"attribute_modifier":"attributeModifier"}]}],"has_relation_modifier":[{"relation_modifier":"relationModifier"},{"relation_modifier":"relationModifier"}]}

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}/relations".format(schemaId='schema_id_example', entityId='entity_id_example'),
    #    headers=headers,
    #    json=relation,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_change_attribute_name_correction(client: TestClient):
    """Test case for change_attribute_name_correction

    change attribute name
    """
    body = 'body_example'

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}/attributes/{attributeId}".format(schemaId='schema_id_example', entityId='entity_id_example', attributeId='attribute_id_example'),
    #    headers=headers,
    #    json=body,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_change_entity_name_correction(client: TestClient):
    """Test case for change_entity_name_correction

    change entity name
    """
    body = 'body_example'

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}".format(schemaId='schema_id_example', entityId='entity_id_example'),
    #    headers=headers,
    #    json=body,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_change_relation_name_correction(client: TestClient):
    """Test case for change_relation_name_correction

    change relation name
    """
    body = 'body_example'

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}/relations/{relationId}".format(schemaId='schema_id_example', entityId='entity_id_example', relationId='relation_id_example'),
    #    headers=headers,
    #    json=body,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_update_attribute_modifiers_correction(client: TestClient):
    """Test case for update_attribute_modifiers_correction

    Update attribute modifiers
    """
    attribute_modifier = [{"attribute_modifier":"attributeModifier"}]

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "PUT",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}/attributes/{attributeId}/modifiers".format(schemaId='schema_id_example', entityId='entity_id_example', attributeId='attribute_id_example'),
    #    headers=headers,
    #    json=attribute_modifier,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_update_entity_modifiers_correction(client: TestClient):
    """Test case for update_entity_modifiers_correction

    Update entity modifiers
    """
    entity_modifier = [{"entity_modifier":"entityModifier"}]

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "PUT",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}/modifiers".format(schemaId='schema_id_example', entityId='entity_id_example'),
    #    headers=headers,
    #    json=entity_modifier,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_update_relation_modifiers_correction(client: TestClient):
    """Test case for update_relation_modifiers_correction

    Update relation modifiers
    """
    relation_modifier = [{"relation_modifier":"relationModifier"}]

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "PUT",
    #    "/schemata/{schemaId}/corrections/entities/{entityId}/relations/{relationId}/modifiers".format(schemaId='schema_id_example', entityId='entity_id_example', relationId='relation_id_example'),
    #    headers=headers,
    #    json=relation_modifier,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

