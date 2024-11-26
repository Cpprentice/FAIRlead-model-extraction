from collections.abc import Iterator
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import TextIO, IO, List, Tuple, Dict

import rdflib
from owlready2 import World, Ontology, sync_reasoner_pellet, DataPropertyClass, ObjectPropertyClass, ThingClass, \
    EXACTLY, MAX, MIN, Restriction
from pydantic import BaseModel
from rdflib import Graph, Namespace, Literal, RDF, OWL, URIRef, RDFS, BNode

from simpler_core.cardinality import merge_cardinalities
from simpler_model import Entity, Cardinality, RelationModifier, EntityModifier, AttributeModifier

relevant_restrictions = {
    EXACTLY, MAX, MIN
}


@dataclass
class SerializationContext:
    ontology: Ontology
    graph: Graph
    classes: List[ThingClass]
    object_properties: List[ObjectPropertyClass]
    data_properties: List[DataPropertyClass]
    prefix_url: str  # TODO we might need a full prefix to type lookup instead
    subject_stack: List[str]


def build_iterative_class_list(ontology: Ontology | World) -> List[ThingClass]:
    class_set = set(ontology.classes())
    new_classes = {1}
    while len(new_classes) > 0:
        next_class_set = {cls for base_cls in class_set for cls in base_cls.subclasses()} | class_set
        new_classes = next_class_set ^ class_set
        class_set = next_class_set

    return list(class_set)


def extract_ontology_concepts(n_triples_streams: List[Tuple[IO, str]]) -> Tuple[
    List[ThingClass],
    List[ObjectPropertyClass],
    List[DataPropertyClass],
    World,
    List[Ontology]
]:
    world = World()
    ontologies = []
    for n_triples_stream, ontology_base_url in n_triples_streams:
        ontologies.append(world.get_ontology(ontology_base_url).load(fileobj=n_triples_stream))

    sync_reasoner_pellet(world)

    classes = sorted(build_iterative_class_list(world), key=lambda x: x.name)
    data_properties = sorted(world.data_properties(), key=lambda x: x.name)
    object_properties = sorted(world.object_properties(), key=lambda x: x.name)

    return classes, object_properties, data_properties, world, ontologies


@contextmanager
def make_n_triples_stream(rdf_like_stream: TextIO) -> Iterator[IO]:
    graph = Graph()
    graph.parse(rdf_like_stream)
    with NamedTemporaryFile('w', newline='', delete_on_close=False, encoding='utf-8') as stream:
        # stream_path_url = Path(stream.name).as_uri().replace('///', '//')
        stream.write(graph.serialize(format='ntriples'))
        stream.close()
        with open(stream.name, 'rb') as binary_stream:
            yield binary_stream


def build_cardinality(restrictions: List[Restriction]) -> Tuple[int, int]:
    cardinality = (0, sys.maxsize)
    for restriction in restrictions:
        if restriction.type == EXACTLY:
            cardinality = merge_cardinalities(cardinality, (restriction.cardinality, restriction.cardinality))
        elif restriction.type == MIN:
            cardinality = merge_cardinalities(cardinality, (restriction.cardinality, sys.maxsize))
        elif restriction.type == MAX:
            cardinality = merge_cardinalities(cardinality, (0, restriction.cardinality))
    return cardinality


def get_cardinality_restrictions(
        domain_class: ThingClass,
        object_prop: ObjectPropertyClass,
        range_class: ThingClass | None
) -> List[Restriction]:
    restrictions = []
    for parent in domain_class.is_a:
        if (isinstance(parent, Restriction)
                and parent.type in relevant_restrictions
                and parent.property is object_prop
                and (parent.value is range_class or range_class is None)):
            restrictions.append(parent)
    return restrictions


def _single_cardinality_stringify(cardinality: Tuple[int, int]) -> str:
    if cardinality[0] == cardinality[1]:
        return str(cardinality[0])
    if cardinality[0] == 0:
        if cardinality[1] == sys.maxsize:
            return 'n'
    if cardinality[1] == sys.maxsize:
        return f'{cardinality[0]}..n'
    return f'{cardinality[0]}..{cardinality[1]}'


def stringify_cardinality(cardinality_a: Tuple[int, int], cardinality_b: Tuple[int, int]) -> List[str]:
    return [
        _single_cardinality_stringify(cardinality_a),
        _single_cardinality_stringify(cardinality_b)
    ]


def _add_concept_data_to_graph(
        graph: Graph,
        concept: BaseModel,
        ero: Namespace,
        data: Namespace,
        ontology_individuals: Dict[type, List[Tuple[BaseModel, URIRef]]]
) -> URIRef:
    if concept.__class__ in ontology_individuals:
        for individual, uri in ontology_individuals[concept.__class__]:
            if individual == concept:
                return uri

    entity_uri = data[uuid.uuid4().hex]
    class_uri = ero[concept.__class__.__name__]
    graph.add((entity_uri, RDF.type, class_uri))
    for field_name in concept.model_fields_set:
        field_alias = concept.model_fields[field_name].alias
        if field_alias is None:
            field_alias = field_name
        field_url = ero[field_alias]
        field_value = getattr(concept, field_name)
        if isinstance(field_value, list):
            for field_value_list_item in field_value:
                # if field_name in ('has_subject_entity', 'has_object_entity'):
                #     graph.
                if field_value_list_item is None:
                    continue
                if isinstance(field_value_list_item, (int, float, str, bool, bytes)):
                    graph.add((entity_uri, field_url, Literal(field_value_list_item)))
                else:
                    inner = _add_concept_data_to_graph(graph, field_value_list_item, ero, data, ontology_individuals)
                    graph.add((entity_uri, field_url, inner))
        else:
            if field_value is None:
                continue
            elif isinstance(field_value, (int, float, str, bool, bytes)):
                graph.add((entity_uri, field_url, Literal(field_value)))
            else:
                inner = _add_concept_data_to_graph(graph, field_value, ero, data, ontology_individuals)
                graph.add((entity_uri, field_url, inner))
    return entity_uri


def build_graph(entities: List[Entity]) -> Graph:
    graph = Graph()
    ero = Namespace('http://iai.kit.edu/vocabularies/entity-relationship-ontology/')
    data = Namespace('http://data/')
    graph.bind('ero', ero)
    graph.bind('data', data)

    # TODO this should be generated from the ontology instead
    ontology_individuals = {
        Cardinality: [
            (Cardinality(cardinality='any'), ero['any']),
            (Cardinality(cardinality='oneOrMore'), ero['oneOrMore']),
            (Cardinality(cardinality='oneOrNone'), ero['oneOrNone']),
            (Cardinality(cardinality='exactlyOne'), ero['exactlyOne']),
        ],
        RelationModifier: [
            (RelationModifier(relation_modifier='identifying'), ero['identifying'])
        ],
        EntityModifier: [
            (EntityModifier(entity_modifier='weak'), ero['weak'])
        ],
        AttributeModifier: [
            (AttributeModifier(attribute_modifier='key'), ero['key'])
        ]
    }

    for entity in entities:
        _add_concept_data_to_graph(graph, entity, ero, data, ontology_individuals)

    # Replace strings with uri refs for relation.has_subject_entity and relation.has_object_entity
    relations = graph.subjects(RDF.type, ero['Relation'])
    entity_lookup = {
        entity_name: entity_uri
        for entity_uri, entity_name in graph.subject_objects(ero['entityName'])
    }

    has_subject_entity = ero['hasSubjectEntity']
    has_object_entity = ero['hasObjectEntity']
    for relation in relations:
        subject_name = list(graph.objects(relation, has_subject_entity))[0]
        object_name = list(graph.objects(relation, has_object_entity))[0]
        graph.add((relation, has_subject_entity, entity_lookup[subject_name]))
        graph.add((relation, has_object_entity, entity_lookup[object_name]))
        graph.remove((relation, has_subject_entity, subject_name))
        graph.remove((relation, has_object_entity, object_name))

    graph_text = graph.serialize(format='n3')
    return graph


def serialize_to_rdf(
        data,
        domain_class: ThingClass,
        ctx: SerializationContext
):
    class_object_properties = {
        object_prop.name: object_prop
        for object_prop in ctx.object_properties
        if any(clause._satisfied_by(domain_class) for clause in object_prop.domain)
    }
    class_data_properties = {
        data_prop.name: data_prop
        for data_prop in ctx.data_properties
        if any(clause._satisfied_by(domain_class) for clause in data_prop.domain)
    }
    subject = ctx.graph.namespace_manager.curie(f':{uuid.uuid4()}')

    for key, value in data.items():
        if key in class_object_properties:
            object_prop = class_object_properties[key]

            range_classes = [
                target_class
                for target_class in ctx.classes
                if any(clause._satisfied_by(target_class) for clause in object_prop.range)
            ]
            found = False
            for range_class in range_classes:
                try:
                    serialize_to_rdf(value, range_class, ctx)
                    found = True
                    break
                except RuntimeError:
                    pass
            if not found:
                raise RuntimeError('No range class works')

        elif key in class_data_properties:
            data_prop = class_data_properties[key]
            if isinstance(value, list):
                for item in value:
                    ctx.graph.add((subject, data_prop, item))
            else:
                ctx.graph.add((subject, data_prop, value))


def build_owl(entities: List[Entity], base_url: str) -> str:
    g = Graph()
    ns = Namespace(base_url)
    g.bind('', ns)

    for entity in entities:
        entity_url = ns[entity.entity_name[0]]
        g.add((entity_url, RDF.type, OWL.Class))
        for attribute in entity.has_attribute:
            attribute_url = ns[attribute.attribute_name[0]]
            g.add((attribute_url, RDF.type, OWL.DatatypeProperty))
            # g.add((attribute_url, RDFS.range, ))
            g.add((attribute_url, RDFS.domain, entity_url))
        for relation in entity.is_subject_in_relation:
            relation_url = ns[relation.relation_name[0]]
            # At this point the relation.has_object_entity should already contain a full URL
            # range_url = ns[relation.has_object_entity]  # So this would result in an incorrect URL
            range_url = URIRef(relation.has_object_entity)
            g.add((relation_url, RDF.type, OWL.ObjectProperty))
            g.add((relation_url, RDFS.range, range_url))
            g.add((relation_url, RDFS.domain, entity_url))
            if relation.subject_cardinality.cardinality not in ['any']:
                restriction = BNode()
                g.add((entity_url, RDFS.subClassOf, restriction))
                g.add((restriction, RDF.type, OWL.Restriction))
                g.add((restriction, OWL.onProperty, relation_url))
                g.add((restriction, OWL.onClass, range_url))
                if relation.subject_cardinality.cardinality in ['oneOrMore']:
                    g.add((restriction, OWL.minQualifiedCardinality, Literal(1)))
                elif relation.subject_cardinality.cardinality in ['exactlyOne']:
                    g.add((restriction, OWL.qualifiedCardinality, Literal(1)))
                elif relation.subject_cardinality.cardinality in ['oneOrNone']:
                    g.add((restriction, OWL.maxQualifiedCardinality, Literal(1)))

    return g.serialize(format='turtle', encoding='utf-8').decode('utf-8')


# def main():
#     with open('spec/0/ero.ttl') as text_stream:
#         with make_n_triples_stream(text_stream) as binary_stream:
#             classes, object_properties, data_properties, world, ontology = \
#                 extract_ontology_concepts(binary_stream, '')
#
#     with open('ontouml/er-test.json', 'r') as stream:
#         example_entity = json.load(stream)
#
#     graph = Graph()
#     ctx = SerializationContext(
#         graph=graph,
#         ontology=ontology,
#         classes=classes,
#         object_properties=object_properties,
#         data_properties=data_properties,
#         prefix_url='http://localhost:7373/schemata/mondial-owl/entities/',
#         subject_stack=[]
#     )
#
#     serialize_to_rdf(example_entity, ontology['Entity'], ctx)
#     xx = 42
#
#
# if __name__ == '__main__':
#     main()
