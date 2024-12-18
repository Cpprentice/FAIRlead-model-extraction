import codecs
import collections
import functools
import io
import shutil
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryFile, NamedTemporaryFile
from typing import List, Dict

from rdflib import Graph, RDF, OWL, RDFS

from simpler_core.cardinality import create_cardinality
from simpler_core.plugin import DataSourcePlugin, DataSourceType
from simpler_core.rdf import (extract_ontology_concepts, make_n_triples_stream, get_cardinality_restrictions,
                              build_cardinality, merge_cardinalities, stringify_cardinality)

try:
    from simpler_model import Entity, Relation, Attribute, AttributeModifier, RelationModifier, EntityModifier

    EntityLink = Relation
except ImportError:
    from simpler_model import Entity, EntityLink, Attribute

entity_query_template = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

select DISTINCT ?s where {{
    {{ 
        ?s rdf:type owl:Class . 
    }}
    UNION 
    {{
        ?s rdf:type rdfs:Class .
    }}
    UNION
    {{
        ?s rdfs:subClassOf ?o 
    }}
    FILTER( STRSTARTS (STR(?s), "{0}") ) .
    # FILTER( regex(str(?s), "{0}") ) .
}}
"""

attribute_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

select DISTINCT ?prop ?domain ?range where {{
    ?prop_class rdfs:subClassOf* rdf:Property .
    ?prop rdf:type ?prop_class .
    FILTER(STRSTARTS(STR(?prop), "{0}"))
    OPTIONAL {{
        ?prop rdfs:domain ?base_domain . 
        {{
            ?domain rdfs:subClassOf* ?base_domain .
        }}
        UNION
        {{
            ?base_domain        owl:disjointUnionOf*    ?domain_union .
            ?domain_union       rdf:rest*/rdf:first     ?domain .
        }} 
        UNION
        {{
            ?base_domain        owl:unionOf*            ?domain_union .
            ?domain_union       rdf:rest*/rdf:first     ?domain .
        }}
    }} .
    OPTIONAL {{
        ?prop rdfs:range ?base_range .
        {{
            ?range rdfs:subClassOf* ?base_range .
        }}
        UNION
        {{
            ?base_range     owl:disjointUnionOf*    ?range_union .
            ?range_union    rdf:rest*/rdf:first     ?range .
        }}
        UNION
        {{
            ?base_range     owl:unionOf*            ?range_union .
            ?range_union    rdf:rest*/rdf:first     ?range .
        }}
        FILTER( !STRSTARTS(STR(?range), "{0}") ) .
    }} .
}}
"""

relation_query_template = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

select DISTINCT ?prop ?domain ?range where {{
    ?prop_class     rdfs:subClassOf*        rdf:Property .
    ?prop           rdf:type                ?prop_class .
    ?prop           rdfs:domain             ?base_domain .
    
    {{
        ?domain         rdfs:subClassOf*        ?base_domain .
    }} UNION {{ 
        ?base_domain    owl:disjointUnionOf*    ?domain_union .
        ?domain_union       rdf:rest*/rdf:first     ?domain .
    }} UNION {{
        ?base_domain    owl:unionOf*            ?domain_union .
        ?domain_union       rdf:rest*/rdf:first     ?domain .
    }}
    
    ?prop           rdfs:range              ?base_range .
    {{
        ?range          rdfs:subClassOf*        ?base_range .
    }}
    UNION
    {{
        ?base_range     owl:disjointUnionOf*    ?range_union .
        ?range_union    rdf:rest*/rdf:first     ?range .
    }}
    UNION
    {{
        ?base_range     owl:unionOf*            ?range_union .
        ?range_union    rdf:rest*/rdf:first     ?range .
    }}
    
    FILTER(STRSTARTS(STR(?prop), "{0}"))
    FILTER(STRSTARTS(STR(?range), "{0}"))
}}
"""


_ = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

select DISTINCT ?prop_class where {
    ?prop_class rdfs:subClassOf* rdf:Property .
}
"""

object_property_query_template = """
SELECT DISTINCT ?subject_type ?relation ?object_type
WHERE {{
    VALUES ?subject_type {{ {0} }} .
    VALUES ?object_type {{ {0} }} .
    VALUES ?relation {{ {1} }} .

    ?s rdf:type ?subject_type .
    ?o rdf:type ?object_type .

    ?s ?relation ?o .
}}
"""

direct_instance_query_template = """
SELECT DISTINCT ?type
WHERE {{
    VALUES ?type {{ {0} }} .
    ?s rdf:type ?type .
}}
"""

property_restrictions_query = """
SELECT DISTINCT ?base ?restriction ?property
WHERE {
    VALUES ?p { owl:onProperty } .
    VALUES ?type { owl:cardinality owl:maxCardinality owl:minCardinality } .
    ?restriction    ?p      ?property ;
                    ?type   _: .
    ?base rdfs:subClassOf ?restriction .
}
"""


class SparqlDataSourceType(DataSourceType):
    name = 'SPARQL'
    inputs = [
        'connector'
    ]


class OwlDataSourceType(DataSourceType):
    name = 'OWL'
    inputs = [
        'ontology',
        'ontology_extension',
        'data'
    ]


class OwlDataSourcePlugin(DataSourcePlugin):

    data_source_type = OwlDataSourceType()

    def _get_entity_dict(self, name: str, only_include_if_data_exists=False) -> Dict[str, List[Entity]]:
        # It seems the ntriples format must have just linux line endings otherwise it just does garbage

        # with open(Path(r'C:\Development\datasets\mondial-database\rdf-mondial\mondial-meta-test.nt'), 'rb') as stream:
        #     ontology = get_ontology('http://www.semwebtech.org/mondial/10/meta#').load(fileobj=stream)
        #     graph = ontology.world.as_rdflib_graph()
        #     type_triples = list(graph.triples((None, RDF.type, None)))
        #     classes = list(ontology.classes())
        #     obj_props = list(ontology.object_properties())
        # with (self.storage.get_data(name) as stream_lookup):
        #     ontology = get_ontology(
        #         'http://www.semwebtech.org/mondial/10/'
        #     ).load(reload=True)
        #     # ).load(fileobj=stream_lookup['ontology-nt'], reload=True)

        # with self.storage.get_data(name) as stream_lookup:
        #     if 'ontology' in stream_lookup:
        #         temp_graph = Graph()
        #         temp_graph.parse(stream_lookup['ontology'])
        #         base_url = temp_graph.namespace_manager.expand_curie(':')
        #         # (Path.cwd() / 'temp.nt').write_text(temp_graph.serialize(format='nt11'))
        #         with NamedTemporaryFile(delete_on_close=False) as ontology_file:
        #             # shutil.copyfileobj(stream_lookup['ontology'], ontology_file)
        #             ontology_file.write(temp_graph.serialize(format='nt11').encode('utf-8'))
        #             ontology_file.seek(0)
        #             # ontology_file.close()
        #             ontology = get_ontology(base_url).load(fileobj=ontology_file)

        # return

        with self.storage.get_data(name) as stream_lookup:
            streams_to_load = {'ontology', 'ontology_extension'} & set(stream_lookup.keys())
            with ExitStack() as stack:
                streams = [
                    stack.enter_context(make_n_triples_stream(stream_lookup[stream_name]))
                    for stream_name in streams_to_load
                ]
                streams_with_url = [
                    (stream, Path(stream.name).as_uri().replace('///', '//'))
                    for stream in streams
                ]
                classes, object_properties, data_properties, world, ontologies = \
                    extract_ontology_concepts(streams_with_url)

            # if 'ontology' in stream_lookup:
            #     with make_n_triples_stream(stream_lookup['ontology']) as n_triples_stream:
            #         stream_path_url = Path(n_triples_stream.name).as_uri().replace('///', '//')
            #         streams.append((n_triples_stream, stream_path_url))
            #         classes, object_properties, data_properties, world, ontologies = \
            #             extract_ontology_concepts([])

            object_property_query = object_property_query_template.format(
                ' '.join(f'<{class_.iri}>' for class_ in classes),
                ' '.join(f'<{prop.iri}>' for prop in object_properties)
            )

            direct_instance_query = direct_instance_query_template.format(
                ' '.join(f'<{class_.iri}>' for class_ in classes)
            )

            object_property_query_data = set()
            direct_instance_query_data = set()
            if only_include_if_data_exists:
                data_graph = Graph()
                data_graph.parse(stream_lookup['data'])
                with NamedTemporaryFile('w', newline='', delete_on_close=False, encoding='utf-8') as stream:
                    stream_path_url = Path(stream.name).as_uri().replace('///', '//')
                    stream.write(data_graph.serialize(format='ntriples'))
                    stream.close()
                    data_ontology = world.get_ontology(stream_path_url).load()

                ontologies[0].imported_ontologies.append(data_ontology)
                object_property_query_data = set(tuple(x) for x in world.sparql(object_property_query))
                direct_instance_query_data = set(x[0] for x in world.sparql(direct_instance_query))

        def type_factory(input_value) -> str:

            # we assume to have one value in the input list
            source_type = input_value[0]
            if source_type == float:
                return 'float'
            if source_type == int:
                return 'int'
            if source_type == bool:
                return 'bool'
            if source_type == str:
                return 'string'
            # TODO date, None
            return 'string'

        entities: Dict[str, List[Entity]] = collections.defaultdict(list)
        for class_ in classes:
            if only_include_if_data_exists:
                # unfortunately instances will also return instances for all the base classes
                # if len(class_.instances()) == 0:
                #     continue
                if class_ not in direct_instance_query_data:
                    continue
            entity = Entity(
                entity_name=[class_.name],
                has_attribute=[],
                has_entity_modifier=None,
                is_object_in_relation=[],
                is_subject_in_relation=[]
            )

            attributes = []
            attributes.append(Attribute(
                attribute_name=['IRI'],
                has_attribute_modifier=[AttributeModifier(attribute_modifier='key')]
            ))

            for data_prop in data_properties:
                if any(clause._satisfied_by(class_) for clause in data_prop.domain):
                    attribute = Attribute(
                        attribute_name=[data_prop.name],
                        has_attribute_modifier=None
                    )
                    attributes.append(attribute)
            entity.has_attribute = attributes

            relations = []
            for object_prop in object_properties:
                general_restrictions = get_cardinality_restrictions(class_, object_prop, None)
                general_cardinality = build_cardinality(general_restrictions)
                # all_cardinalities = [general_cardinality]

                # TODO reconsider any instead of all here - i think there was a reason for it
                #  - multiple domain triples mean the intersection of all domains not the union - so all seems correct
                if all(clause._satisfied_by(class_) for clause in object_prop.domain):
                    for target_class in [
                        target_class
                        for target_class in classes
                        if all(clause._satisfied_by(target_class) for clause in object_prop.range)
                    ]:
                        if only_include_if_data_exists:
                            # if target_class not in direct_instance_query_data:
                            #     continue
                            # old implementation tracking property occurrence is now replaced by
                            #  filtering if target class has instances <-- and has been reversed because it
                            #  caused thousands of more relations
                            if ((class_, object_prop, target_class) not in object_property_query_data and
                                    (target_class, object_prop.inverse_property, class_) not in
                                    object_property_query_data):
                                continue
                            x = 42

                        restrictions = get_cardinality_restrictions(class_, object_prop, target_class)
                        specific_cardinality = build_cardinality(restrictions)
                        all_cardinalities = [general_cardinality, specific_cardinality]

                        combined_cardinality = functools.reduce(merge_cardinalities, all_cardinalities,
                                                                all_cardinalities[0])

                        inverse_relation = None
                        if object_prop.inverse_property is not None:
                            inverse_restrictions = get_cardinality_restrictions(
                                target_class, object_prop.inverse_property, class_)
                            inverse_cardinality = build_cardinality(inverse_restrictions)
                            inverse_relation = object_prop.inverse_property.name
                        else:
                            inverse_cardinality = build_cardinality([])

                        relation = Relation(
                            relation_name=[object_prop.name],
                            has_object_entity=target_class.name,
                            has_subject_entity=class_.name,
                            object_cardinality=create_cardinality(combined_cardinality),
                            subject_cardinality=create_cardinality(inverse_cardinality),
                            has_attribute=[],
                            has_relation_modifier=[RelationModifier(relation_modifier='identifying')] \
                                if inverse_cardinality[0] > 0 else None,
                            inverse_relation=inverse_relation
                        )
                        if relation.has_relation_modifier is not None:
                            make_weak = True
                        relations.append(relation)
            entity.is_subject_in_relation = relations

            # if make_weak:
            #     entity.has_entity_modifier = [EntityModifier(entity_modifier='weak')]

            entities[entity.entity_name[0]].append(entity)

        for local_entity_list in entities.values():
            for entity in local_entity_list:
                for relation in entity.is_subject_in_relation:
                    target_entity = entities[relation.has_object_entity][0]
                    if relation.has_relation_modifier is not None:
                        target_entity.has_entity_modifier = [EntityModifier(entity_modifier='weak')]

        return entities

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        entity_lookup = self._get_entity_dict(name, only_include_if_data_exists=True)
        return [
            entity
            for entity_list in entity_lookup.values()
            for entity in entity_list
        ]

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass


class SparqlDataSourcePlugin(DataSourcePlugin):

    data_source_type = SparqlDataSourceType()

    def get_connector(self, name: str):
        with self.storage.get_data(name) as data_lookup:
            connector_stream = codecs.getreader('utf-8')(data_lookup['connector'])
            connector_string = connector_stream.read()
        # TODO some code to produce an interface to send queries to a SPARQL endpoint
        return None

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        connector = self.get_connector(name)
        result = connector.run_query(entity_query_template.format(connector.base_url))

        # TODO query for relations, attributes and keys

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass
