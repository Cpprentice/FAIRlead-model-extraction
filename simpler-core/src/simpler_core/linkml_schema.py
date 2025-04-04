from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.utils.schema_builder import SchemaBuilder

from simpler_model import Entity


def convert_er_to_linkml(entities: list[Entity]) -> SchemaDefinition:
    schema_builder = SchemaBuilder(
        'ExtractedSchema'
    )
    for entity in entities:
        attribute_names = [
            attribute.attribute_name[0]
            for attribute in entity.has_attribute
        ]
        for attribute_name in attribute_names:
            schema_builder.add_slot(attribute_name)
        schema_builder.add_class(entity.entity_name[0], slots=attribute_names)

    return schema_builder.schema
