import copy

from jsonpath import JSONPatch, JSONPointer
from jsonpath.patch import OpAddAp
from linkml_runtime import SchemaView
from linkml_runtime.linkml_model import SchemaDefinition
from oemetadata.v2.v20.template import OEMETADATA_V20_TEMPLATE


def convert_schema_to_oemetadata(schema_definition: SchemaDefinition) -> dict:
    oemetadata_template = copy.deepcopy(OEMETADATA_V20_TEMPLATE)
    resource_template = oemetadata_template['resources'][0]
    field_template = resource_template['schema']['fields'][0]
    is_about_template = field_template['isAbout'][0]
    value_ref_template = field_template['valueReference'][0]

    del resource_template["schema"]["fields"][0]
    del field_template['isAbout'][0]
    del field_template['valueReference'][0]
    del oemetadata_template['resources'][0]

    # resources_pointer = JSONPointer('/resources')
    # last_resource_pointer = resources_pointer / '-'
    # fields_pointer = last_resource_pointer / 'schema' / 'fields'
    # last_field_pointer = fields_pointer / '-'
    # annotations_pointer = last_field_pointer / 'isAbout'
    # last_annotation_pointer = annotations_pointer / '-'
    #
    # new_resource_op = OpAddAp(last_resource_pointer, resource_template)
    # new_field_op = OpAddAp(last_field_pointer, field_template)
    # new_annotation_op = OpAddAp(last_annotation_pointer, is_about_template)

    view = SchemaView(schema_definition)
    result = copy.deepcopy(oemetadata_template)
    # patch_runner = JSONPatch(unicode_escape=False)
    # patch_runner.add('', oemetadata_template)

    # patch_runner.add('/name', schema_definition.name)
    # patch_runner.add('/@id', schema_definition.id)
    result['name'] = schema_definition.name
    result['@id'] = schema_definition.id

    for class_name, class_ in view.all_classes().items():
        # patch_runner.ops.append(new_resource_op)
        # patch_runner.add(last_resource_pointer / 'name', class_name)
        # patch_runner.add(last_resource_pointer / '@id', class_name)
        resource = copy.deepcopy(resource_template)
        resource['name'] = class_name
        resource['@id'] = class_name

        result['resources'].append(resource)

        for slot_name in view.class_slots(class_name):
            slot = view.induced_slot(slot_name, class_name)
            # patch_runner.ops.append(new_field_op)
            # patch_runner.add(last_field_pointer / 'name', slot_name)
            field = copy.deepcopy(field_template)
            field['name'] = slot_name
            resource['schema']['fields'].append(field)

            if slot.unit is not None:
                # patch_runner.add(last_field_pointer / 'unit', slot.unit.exact_mappings[0])
                field['unit'] = slot.unit.exact_mappings[0]
            for mapping in slot.exact_mappings:
                # patch_runner.ops.append(new_annotation_op)
                # # patch_runner.add(last_annotations_pointer / 'name', '')  # TODO also resolve this with terminology service?
                # patch_runner.add(last_annotation_pointer / '@id', mapping)
                is_about = copy.deepcopy(is_about_template)
                # is_about['name'] = ''
                is_about['@id'] = mapping
                field['isAbout'].append(is_about)

    # result= patch_runner.apply({})
    return result
