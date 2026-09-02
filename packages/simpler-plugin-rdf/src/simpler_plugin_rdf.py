import codecs
import collections
import functools
import io
import shutil
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryFile, NamedTemporaryFile, TemporaryDirectory
from typing import List, Dict
from zipfile import ZipFile

from linkml_runtime.linkml_model import SchemaDefinition, ClassDefinition, SlotDefinition
from linkml_runtime.utils.schema_builder import SchemaBuilder
from owlready2 import onto_path, World, PREDEFINED_ONTOLOGIES, sync_reasoner_pellet, Ontology
from rdflib import Graph, RDF, OWL, RDFS

from fairlead_core.cardinality import create_cardinality
from fairlead_core.plugin import DataSourcePlugin, DataSourceType, InputFlag
from fairlead_core.rdf import (extract_ontology_concepts, make_n_triples_stream, get_cardinality_restrictions,
                               build_cardinality, merge_cardinalities, stringify_cardinality,
                               build_iterative_class_list)
from fairlead_core.storage import FileMapSettings

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
        ('connector', InputFlag.TEXT | InputFlag.SECURE)
    ]


class OwlDataSourceType(DataSourceType):
    name = 'OWL'
    inputs = [
        ('ontology', InputFlag.TEXT),
        ('ontology_extension', InputFlag.TEXT),
        ('data', InputFlag.TEXT),
        ('import', InputFlag.TEXT)
    ]


class OwlDataSourcePlugin(DataSourcePlugin):

    data_source_type = OwlDataSourceType()

    def _load_all_non_data_inputs(self, name: str) -> tuple[World, list[Ontology]]:
        world = World()
        file_map = FileMapSettings(self.storage, name)

        main_ontologies = []

        for file_name, factory in file_map.get_input_stream_factories("import").items():
            with factory() as onto_stream, make_n_triples_stream(onto_stream) as triples_stream:
                ontology = world.get_ontology('temp').load(fileobj=triples_stream, only_local=True)
            PREDEFINED_ONTOLOGIES[ontology.base_iri] = ontology

        for file_name, factory in file_map.get_input_stream_factories("ontology").items():
            with factory() as onto_stream, make_n_triples_stream(onto_stream) as triples_stream:
                ontology_base_url = Path(triples_stream.name).as_uri().replace('///', '//')
                ontology = world.get_ontology(ontology_base_url).load(fileobj=triples_stream, only_local=True)
                main_ontologies.append(ontology)

        for file_name, factory in file_map.get_input_stream_factories("ontology_extension").items():
            with factory() as onto_stream, make_n_triples_stream(onto_stream) as triples_stream:
                ontology_base_url = Path(triples_stream.name).as_uri().replace('///', '//')
                ontology = world.get_ontology(ontology_base_url).load(fileobj=triples_stream, only_local=True)
                main_ontologies.append(ontology)

        # sync_reasoner_pellet(world)  # TODO pellet complained about an old java version - maybe I need to set my env to a newer java
        return world, main_ontologies

    @staticmethod
    def _extract_ontology_concepts(world: World):
        classes = sorted(build_iterative_class_list(world), key=lambda x: x.name)
        data_properties = sorted(world.data_properties(), key=lambda x: x.name)
        object_properties = sorted(world.object_properties(), key=lambda x: x.name)

        return classes, object_properties, data_properties

    def _get_entity_dict(self, name: str, only_include_if_data_exists=False) -> Dict[str, List[Entity]]:
        # It seems the ntriples format must have just linux line endings otherwise it just does garbage

        world, ontologies = self._load_all_non_data_inputs(name)
        # with self.storage.get_data(name) as stream_lookup, TemporaryDirectory() as import_directory:
        #     if 'imports' in stream_lookup:
        #         with ZipFile(stream_lookup['imports']) as import_zip:
        #             import_zip.extractall(import_directory)
        #         # onto_path.append(import_directory)
        #
        #         for import_ontology_path in Path(import_directory).glob('*.ttl'):
        #             with open(import_ontology_path, 'rb') as onto_stream:
        #                 with make_n_triples_stream(onto_stream) as triples_stream:
        #                     ontology = world.get_ontology('temp').load(fileobj=triples_stream, only_local=True)
        #             PREDEFINED_ONTOLOGIES[ontology.base_iri] = ontology
        #
        #     streams_to_load = {'ontology', 'ontology_extension'} & set(stream_lookup.keys())
        #     with ExitStack() as stack:
        #         streams = [
        #             stack.enter_context(make_n_triples_stream(stream_lookup[stream_name]))
        #             for stream_name in streams_to_load
        #         ]
        #         streams_with_url = [
        #             (stream, Path(stream.name).as_uri().replace('///', '//'))
        #             for stream in streams
        #         ]
        #         classes, object_properties, data_properties, world, ontologies = \
        #             extract_ontology_concepts(streams_with_url, world)
        #
        #     # if 'ontology' in stream_lookup:
        #     #     with make_n_triples_stream(stream_lookup['ontology']) as n_triples_stream:
        #     #         stream_path_url = Path(n_triples_stream.name).as_uri().replace('///', '//')
        #     #         streams.append((n_triples_stream, stream_path_url))
        #     #         classes, object_properties, data_properties, world, ontologies = \
        #     #             extract_ontology_concepts([])

        classes, object_properties, data_properties = self._extract_ontology_concepts(world)

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

            file_map = FileMapSettings(self.storage, name)
            for file_name, factory in file_map.get_input_stream_factories("data").items():
                with factory() as onto_stream, make_n_triples_stream(onto_stream) as triples_stream:
                    data_base_url = Path(triples_stream.name).as_uri().replace('///', '//')
                    data_ontology = world.get_ontology(data_base_url).load(fileobj=triples_stream, only_local=True)

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

    def get_all_entities(self, name: str) -> List[Entity]:
        entity_lookup = self._get_entity_dict(name, only_include_if_data_exists=False)
        return [
            entity
            for entity_list in entity_lookup.values()
            for entity in entity_list
        ]

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass

    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        pass

    def get_schema(self, name: str) -> SchemaDefinition:
        world, ontologies = self._load_all_non_data_inputs(name)
        classes, object_properties, datatype_properties = self._extract_ontology_concepts(world)

        schema_builder = SchemaBuilder(name)
        schema_builder.add_defaults()

        # TODO do we need to build multiple schemas here e.g. for DCAT3 and PROV in parallel
        for cls in classes:
            schema_builder.add_class(ClassDefinition(
                name=cls.name,
                class_uri=cls.iri
            ))

        for prop in object_properties:
            schema_builder.add_slot(SlotDefinition(
                name=prop.name,
                # range=prop.range,
                # domain=prop.domain,
                slot_uri=prop.iri
            ))

        for prop in datatype_properties:
            schema_builder.add_slot(SlotDefinition(
                name=prop.name,
                # range=prop.range,
                # domain=prop.domain,
                slot_uri=prop.iri
            ))
        return schema_builder.schema


class SparqlDataSourcePlugin(DataSourcePlugin):

    data_source_type = SparqlDataSourceType()

    def get_connector(self, name: str):
        with self.storage.get_data(name) as data_lookup:
            connector_stream = codecs.getreader('utf-8')(data_lookup['connector'])
            connector_string = connector_stream.read()
        # TODO some code to produce an interface to send queries to a SPARQL endpoint
        return None

    def get_all_entities(self, name: str) -> List[Entity]:
        connector = self.get_connector(name)
        result = connector.run_query(entity_query_template.format(connector.base_url))

        # TODO query for relations, attributes and keys

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass
