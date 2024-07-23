import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from tempfile import NamedTemporaryFile
from typing import TextIO, IO, List, Tuple

from owlready2 import World, Ontology, sync_reasoner_pellet, DataPropertyClass, ObjectPropertyClass, ThingClass, \
    EXACTLY, MAX, MIN, Restriction
from rdflib import Graph


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


def build_iterative_class_list(ontology: Ontology) -> List[ThingClass]:
    class_set = set(ontology.classes())
    new_classes = {1}
    while len(new_classes) > 0:
        next_class_set = {cls for base_cls in class_set for cls in base_cls.subclasses()} | class_set
        new_classes = next_class_set ^ class_set
        class_set = next_class_set

    return list(class_set)


def extract_ontology_concepts(n_triples_stream: IO, ontology_base_url: str) -> Tuple[
    List[ThingClass],
    List[ObjectPropertyClass],
    List[DataPropertyClass],
    World,
    Ontology
]:
    world = World()
    ontology = world.get_ontology(ontology_base_url).load(fileobj=n_triples_stream)

    sync_reasoner_pellet(world)

    classes = sorted(build_iterative_class_list(ontology), key=lambda x: x.name)
    data_properties = sorted(ontology.data_properties(), key=lambda x: x.name)
    object_properties = sorted(ontology.object_properties(), key=lambda x: x.name)

    return classes, object_properties, data_properties, world, ontology


@contextmanager
def make_n_triples_stream(rdf_like_stream: TextIO) -> IO:
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


def merge_cardinalities(c_a: Tuple[int, int], c_b: Tuple[int, int]) -> Tuple[int, int]:
    min_a, max_a = c_a
    min_b, max_b = c_b
    if min_a != min_b and min_a != 0 and min_b != 0:
        raise ValueError('The cardinalities to merge have both non-zero min values that are not equal')
    if max_a != max_b and max_a != sys.maxsize and max_b != sys.maxsize:
        raise ValueError('The cardinalities to merge have both non-limited max values that are not equal')
    return max(min_a, min_b), min(max_a, max_b)


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
