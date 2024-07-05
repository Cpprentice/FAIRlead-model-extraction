import collections
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Tuple, List, Dict, IO, TextIO

from owlready2 import World, sync_reasoner_pellet, Ontology, ThingClass, EXACTLY, MAX, MIN, ObjectPropertyClass, \
    DataPropertyClass
from rdflib import Graph

# object_property_query_template = """
# SELECT DISTINCT ?subject_type ?relation ?object_type
# WHERE {{
#     VALUES ?subject_type {{ {0} }} .
#     VALUES ?object_type {{ {0} }} .
#     VALUES ?relation {{ {1} }} .
#
#     ?s rdf:type ?subject_type .
#     ?o rdf:type ?object_type .
#
#     ?s ?relation ?o .
# }}
# """

# direct_instance_query_template = """
# SELECT DISTINCT ?type
# WHERE {{
#     VALUES ?type {{ {0} }} .
#     ?s rdf:type ?type .
# }}
# """

property_restrictions_query = """
SELECT DISTINCT ?base ?restriction ?property ?inverse_prop ?partial_range
WHERE {
    VALUES ?p { owl:onProperty } .
    VALUES ?type { owl:cardinality owl:maxCardinality owl:minCardinality 
                   owl:qualifiedCardinality owl:maxQualifiedCardinality owl:minQualifiedCardinality } .
    ?restriction    ?p      ?property ;
                    ?type   _: .
    ?base rdfs:subClassOf ?restriction .
    OPTIONAL { ?property owl:inverseOf ?inverse_prop . } .
    OPTIONAL { ?restriction owl:onClass ?partial_range . } .
}
"""

relevant_restrictions = {
    EXACTLY, MAX, MIN
}


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
    Dict[Tuple[ThingClass, ObjectPropertyClass, ThingClass | None], List[List[str]]],
    World,
    Ontology
]:
    world = World()
    ontology = world.get_ontology(ontology_base_url).load(fileobj=n_triples_stream)

    sync_reasoner_pellet(world)

    classes = sorted(build_iterative_class_list(ontology), key=lambda x: x.name)
    data_properties = sorted(ontology.data_properties(), key=lambda x: x.name)
    object_properties = sorted(ontology.object_properties(), key=lambda x: x.name)

    # object_property_query = object_property_query_template.format(
    #     ' '.join(f'<{class_.iri}>' for class_ in classes),
    #     ' '.join(f'<{prop.iri}>' for prop in object_properties)
    # )

    # direct_instance_query = direct_instance_query_template.format(
    #     ' '.join(f'<{class_.iri}>' for class_ in classes)
    # )

    property_restrictions = collections.defaultdict(list)
    for domain, restriction, prop, inverse, partial_range in world.sparql(property_restrictions_query):
        if restriction.type in relevant_restrictions:
            cardinality = str(restriction.cardinality) if restriction.cardinality is not None else 'n'
            if restriction.type == EXACTLY:
                property_restrictions[(domain, prop, partial_range)].append([cardinality, cardinality])
            elif restriction.type == MIN:
                property_restrictions[(domain, prop, partial_range)].append([cardinality, 'n'])
            elif restriction.type == MAX:
                property_restrictions[(domain, prop, partial_range)].append(['0', cardinality])
            else:
                raise NotImplementedError('restriction type not supported')
            # TODO we should consider handling the inverse properties - for that we must evaluate what it means
            #  for the inverse prop if the base prop has e.g. a min cardinality of 1
            # TODO we do not consider ranges correctly yet

    if any(len(l) != 1 for l in property_restrictions.values()):
        raise RuntimeError(
            'restriction has multiple definitions for cardinality on the same domain / property pair')
    property_restrictions = {
        key: l[0]
        for key, l in property_restrictions.items()
    }

    return classes, object_properties, data_properties, property_restrictions, world, ontology


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
