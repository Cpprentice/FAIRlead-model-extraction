# coding: utf-8

"""
    Schema API - OpenAPI 3.1

    This is a Schema extraction API based on the OpenAPI 3.1 specification.  You can find out more about Swagger at [https://swagger.io](https://swagger.io). 

    The version of the OpenAPI document: 0.2.0
    Contact: philipp.schmurr@kit.edu
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


from __future__ import annotations
import pprint
import re  # noqa: F401
import json




from pydantic import BaseModel, ConfigDict, Field, StrictStr
from typing import Any, ClassVar, Dict, List, Optional
from typing_extensions import Annotated
from simpler_model.models.attribute import Attribute
from simpler_model.models.cardinality import Cardinality
from simpler_model.models.relation_modifier import RelationModifier
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

class Relation(BaseModel):
    """
    Relation
    """ # noqa: E501
    has_object_entity: Optional[Any] = Field(alias="hasObjectEntity")
    has_subject_entity: Optional[Any] = Field(alias="hasSubjectEntity")
    object_cardinality: Cardinality = Field(alias="objectCardinality")
    subject_cardinality: Cardinality = Field(alias="subjectCardinality")
    relation_name: Annotated[List[StrictStr], Field(min_length=1)] = Field(alias="relationName")
    has_attribute: Optional[List[Attribute]] = Field(default=None, alias="hasAttribute")
    has_relation_modifier: Optional[List[RelationModifier]] = Field(default=None, alias="hasRelationModifier")
    additional_properties: Dict[str, Any] = {}
    __properties: ClassVar[List[str]] = ["hasObjectEntity", "hasSubjectEntity", "objectCardinality", "subjectCardinality", "relationName", "hasAttribute", "hasRelationModifier"]

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }


    def to_str(self) -> str:
        """Returns the string representation of the model using alias"""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias"""
        # TODO: pydantic v2: use .model_dump_json(by_alias=True, exclude_unset=True) instead
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Create an instance of Relation from a JSON string"""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the model using alias.

        This has the following differences from calling pydantic's
        `self.model_dump(by_alias=True)`:

        * `None` is only added to the output dict for nullable fields that
          were set at model initialization. Other fields with value `None`
          are ignored.
        * Fields in `self.additional_properties` are added to the output dict.
        """
        _dict = self.model_dump(
            by_alias=True,
            exclude={
                "additional_properties",
            },
            exclude_none=True,
        )
        # override the default output from pydantic by calling `to_dict()` of each item in has_attribute (list)
        _items = []
        if self.has_attribute:
            for _item in self.has_attribute:
                if _item:
                    _items.append(_item.to_dict())
            _dict['hasAttribute'] = _items
        # puts key-value pairs in additional_properties in the top level
        if self.additional_properties is not None:
            for _key, _value in self.additional_properties.items():
                _dict[_key] = _value

        # set to None if has_object_entity (nullable) is None
        # and model_fields_set contains the field
        if self.has_object_entity is None and "has_object_entity" in self.model_fields_set:
            _dict['hasObjectEntity'] = None

        # set to None if has_subject_entity (nullable) is None
        # and model_fields_set contains the field
        if self.has_subject_entity is None and "has_subject_entity" in self.model_fields_set:
            _dict['hasSubjectEntity'] = None

        return _dict

    @classmethod
    def from_dict(cls, obj: Dict) -> Self:
        """Create an instance of Relation from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "hasObjectEntity": obj.get("hasObjectEntity"),
            "hasSubjectEntity": obj.get("hasSubjectEntity"),
            "objectCardinality": obj.get("objectCardinality"),
            "subjectCardinality": obj.get("subjectCardinality"),
            "relationName": obj.get("relationName"),
            "hasAttribute": [Attribute.from_dict(_item) for _item in obj.get("hasAttribute")] if obj.get("hasAttribute") is not None else None,
            "hasRelationModifier": obj.get("hasRelationModifier")
        })
        # store additional fields in additional_properties
        for _key in obj.keys():
            if _key not in cls.__properties:
                _obj.additional_properties[_key] = obj.get(_key)

        return _obj


