from linkml_runtime import SchemaView
from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition, Element
from linkml_runtime.linkml_model.units import UnitOfMeasure
from pydantic import BaseModel

from simpler_model import ClassDefinitionView, SlotDefinitionView, OntologicalAnnotation, Unit


def fetch_matching_attributes(domain_model: object, target_view: type[BaseModel]) -> dict:
    return {
        attribute_name: getattr(domain_model, attribute_name, None)
        for attribute_name in target_view.model_fields.keys()
    }


def build_annotations(element: Element) -> list[OntologicalAnnotation]:
    return [
        OntologicalAnnotation(operator='exact_mapping', iri=url)
        for url in element.exact_mappings
    ] + [
        OntologicalAnnotation(operator='close_mapping', iri=url)
        for url in element.close_mappings
    ] + [
        OntologicalAnnotation(operator='related_mapping', iri=url)
        for url in element.related_mappings
    ] + [
        OntologicalAnnotation(operator='narrow_mapping', iri=url)
        for url in element.narrow_mappings
    ] + [
        OntologicalAnnotation(operator='broad_mapping', iri=url)
        for url in element.broad_mappings
    ]


def make_class_definition_view(class_def: ClassDefinition, schema_view: SchemaView) -> ClassDefinitionView:
    sorted_attributes = sorted(
        (attribute for attribute in class_def.attributes.values()),
        key=lambda attribute: attribute.rank if attribute.rank is not None else 0
    )
    sorted_attribute_names = [x.name for x in sorted_attributes]

    kwargs = fetch_matching_attributes(class_def, ClassDefinitionView) | dict(
        attributes={
            attribute_name: make_slot_definition_view(
                schema_view.induced_slot(attribute_name, class_def.name),
                schema_view
            )
            # for attribute_name in class_def.attributes.keys()
            for attribute_name in sorted_attribute_names
        },
        relations={
            slot_name: make_slot_definition_view(schema_view.induced_slot(slot_name, class_def.name), schema_view)
            for slot_name in class_def.slots
        },
        annotations=build_annotations(class_def)
    )
    return ClassDefinitionView(**kwargs)


def make_unit(linkml_unit: UnitOfMeasure | None) -> Unit | None:
    if linkml_unit is None:
        return None
    return Unit(
        id=linkml_unit.exact_mappings[0],
        symbol=linkml_unit.symbol,
        description=linkml_unit.descriptive_name
    )


def make_slot_definition_view(slot_def: SlotDefinition | str, schema_view: SchemaView) -> SlotDefinitionView:
    if isinstance(slot_def, str):
        slot_def = schema_view.get_slot(slot_def)

    kwargs = fetch_matching_attributes(slot_def, SlotDefinitionView) | dict(
        key=slot_def.key or slot_def.identifier or False,
        annotations=build_annotations(slot_def),
        unit=make_unit(slot_def.unit)
    )

    # Workaround for the moment because the pydantic validator does only accept a missing value not a None
    if slot_def.unit is None:
        del kwargs['unit']

    return SlotDefinitionView(**kwargs)
