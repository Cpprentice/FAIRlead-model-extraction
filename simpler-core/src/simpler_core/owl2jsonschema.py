import functools
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Type, Set

from owlready2 import ThingClass, ObjectPropertyClass, Restriction, EXACTLY, MIN, MAX, DataPropertyClass, Ontology, \
    World, sync_reasoner_pellet

from simpler_core.rdf import make_n_triples_stream, extract_ontology_concepts, \
    get_cardinality_restrictions, build_cardinality, merge_cardinalities


@dataclass
class ConversionSettings:
    ontology: Ontology
    exclude_non_base_iri_concepts: bool = True
    link_uri_pattern: str = ''
    force_link_on: Set[ThingClass] = field(default_factory=set)
    exclude_concept: Set[ThingClass | DataPropertyClass | ObjectPropertyClass] = field(default_factory=set)


def build_iterative_class_list(ontology: Ontology) -> List[ThingClass]:
    class_set = set(ontology.classes())
    new_classes = {1}
    while len(new_classes) > 0:
        next_class_set = {cls for base_cls in class_set for cls in base_cls.subclasses()} | class_set
        new_classes = next_class_set ^ class_set
        class_set = next_class_set

    return list(class_set)


def make_object_schema(class_: ThingClass, opt: ConversionSettings) -> Dict | None:
    if opt.exclude_non_base_iri_concepts and not class_.iri.startswith(opt.ontology.base_iri):
        return None

    if class_ in opt.exclude_concept:
        return None

    object_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        # "$id": class_.iri,
        "$id": class_.name,
        "title": class_.name,
        # "description": class_.,
        "type": "object"
    }

    individuals = class_.instances()
    if individuals:
        prep_object_schema_for_props(object_schema)

        prop_name = class_.name[0].lower() + class_.name[1:]
        object_schema['properties'][prop_name] = {'type': 'string'}
        object_schema['required'].append(prop_name)

        object_schema['enum'] = [
            {class_.name: x.name}
            for x in individuals
        ]

    return object_schema


def prep_object_schema_for_props(object_schema: Dict):
    if 'properties' not in object_schema:
        object_schema['properties'] = {}

    if 'required' not in object_schema:
        object_schema['required'] = []


def json_schema_type_factory(python_type: Type):
    if python_type == str:
        return 'string'
    if python_type == int:
        return 'number'
    raise ValueError(f'Unsupported python type "{python_type}"')


def inject_data_prop(
        object_schema: Dict,
        domain_class: ThingClass,
        data_prop: DataPropertyClass,
        opt: ConversionSettings
):
    if opt.exclude_non_base_iri_concepts and not data_prop.iri.startswith(opt.ontology.base_iri):
        return
    if data_prop in opt.exclude_concept:
        return

    prep_object_schema_for_props(object_schema)

    # range_classes = [
    #     json_schema_type_factory(t)
    #     for t in data_prop.range
    # ]
    range_classes = list(data_prop.range)

    handle_prop_content(object_schema, domain_class, data_prop, range_classes, opt)


def inject_object_prop(
        object_schema: Dict,
        domain_class: ThingClass,
        object_prop: ObjectPropertyClass,
        classes: List[ThingClass],
        opt: ConversionSettings
):
    if opt.exclude_non_base_iri_concepts and not object_prop.iri.startswith(opt.ontology.base_iri):
        return

    if object_prop in opt.exclude_concept:
        return

    prep_object_schema_for_props(object_schema)

    relevant_range_classes = [
        target_class
        for target_class in classes
        if any(clause._satisfied_by(target_class) for clause in object_prop.range)
        and (
           not opt.exclude_non_base_iri_concepts
           or (
                   opt.exclude_non_base_iri_concepts
                   and target_class.iri.startswith(target_class.namespace.ontology.base_iri)
           )
        )
    ]

    handle_prop_content(object_schema, domain_class, object_prop, relevant_range_classes, opt)


def handle_prop_content(
        object_schema: Dict,
        domain_class: ThingClass,
        prop: ObjectPropertyClass | DataPropertyClass,
        relevant_range_classes: List[ThingClass] | List[str],
        opt: ConversionSettings
):
    general_restrictions = get_cardinality_restrictions(domain_class, prop, None)
    general_cardinality = build_cardinality(general_restrictions)
    all_cardinalities = [general_cardinality]

    for range_class in relevant_range_classes:
        restrictions = get_cardinality_restrictions(domain_class, prop, range_class)
        specific_cardinality = build_cardinality(restrictions)
        all_cardinalities.append(specific_cardinality)

    try:
        combined_cardinality = functools.reduce(merge_cardinalities, all_cardinalities, all_cardinalities[0])
        can_combine = True
    except ValueError:
        can_combine = False

    if can_combine:
        # this means we have one array for all subtypes
        object_schema['properties'][prop.name] = build_one_of_array(
            combined_cardinality,
            relevant_range_classes,
            opt
        )
        if combined_cardinality[0] > 0:
            object_schema['required'].append(prop.name)
    else:
        # this means we have distinct array with homogenous types (and other cardinalities each)
        one_of = []
        object_schema['properties'][prop.name] = {
            'oneOf': one_of
        }
        for range_class, cardinality in zip(relevant_range_classes, all_cardinalities[1:]):
            one_of.append(build_one_of_array(cardinality, [range_class], opt))

        if any(c[0] > 0 for c in all_cardinalities[1:]):
            object_schema['required'].append(prop.name)


def build_one_of_array(
        cardinality: Tuple[int, int],
        classes: List[ThingClass] | List[str],
        opt: ConversionSettings
) -> Dict:
    items = []
    for class_ in classes:
        if isinstance(class_, ThingClass):
            if class_ in opt.force_link_on:
                items.append({'format': 'url', 'pattern': opt.link_uri_pattern})
            else:
                # items.append({'$ref': class_.iri})
                items.append({'$ref': f'{class_.name}.json'})
                # items.append({'$ref': class_.name})
        else:
            items.append({'type': json_schema_type_factory(class_)})
    if cardinality == (0, 1) or cardinality == (1, 1):
        if cardinality == (0, 1):
            items += {'type': 'null'}

        if len(items) == 1:
            return items[0]

        field_spec = {
            'oneOf': items,
        }
        if cardinality == (0, 1):
            field_spec['default'] = None
        return field_spec

    array = {
        'type': 'array',
        # 'items': {
            # 'oneOf': items
            # 'oneOf': [
            #     {'$ref': class_.iri} if isinstance(class_, ThingClass) else {'type': class_}
            #     for class_ in classes
            # ]
        # }
    }

    if len(items) == 1:
        array['items'] = items[0]
    else:
        array['items'] = {
            'oneOf': items
        }

    if cardinality[0] > 0:
        array['minItems'] = cardinality[0]
    else:
        array['default'] = []
    if cardinality[1] < sys.maxsize:
        array['maxItems'] = cardinality[1]
    return array


# def is_array_relation(object_prop: ObjectPropertyClass, restrictions: List[Restriction]) -> bool:
#     if len(restrictions) == 0:
#         return True
#     exact_restrictions = [r for r in restrictions if r.type == EXACTLY]
#     if any(r.cardinality > 1 for r in exact_restrictions):
#         return True


def main():
    _, owl_file_path, target_folder = sys.argv
    owl_file_path = Path(owl_file_path)
    target_folder = Path(target_folder)

    target_folder.mkdir(exist_ok=True)

    with (open(owl_file_path, 'r') as stream):
        with make_n_triples_stream(stream) as n_triples_stream:
            stream_path_url = Path(n_triples_stream.name).as_uri().replace('///', '//')
            classes, object_properties, data_properties, world, ontology = \
                extract_ontology_concepts(n_triples_stream, stream_path_url)

    opt = ConversionSettings(
        ontology=ontology,
        link_uri_pattern='http://localhost:7373/schemata/[^/]+/entities/[^/]+',
        force_link_on={ontology['Entity']},
        exclude_concept={ontology['isAttributeOf']}
    )

    # only_base_iri_concepts = True
    # force_link_on_object_prop_range = {ontology['Entity']}

    object_schemas = []
    for class_ in classes:
        object_schema = make_object_schema(class_, opt)

        if object_schema is None:
            continue

        for object_prop in object_properties:
            if any(clause._satisfied_by(class_) for clause in object_prop.domain):
                inject_object_prop(
                    object_schema,
                    class_,
                    object_prop,
                    classes,
                    opt
                )

        for data_prop in data_properties:
            if any(clause._satisfied_by(class_) for clause in data_prop.domain):
                inject_data_prop(object_schema, class_, data_prop, opt)

        object_schemas.append(object_schema)
        with open(target_folder / f'{class_.name}.json', 'w') as stream:
            json.dump(object_schema, stream, indent=4)


if __name__ == '__main__':
    main()
