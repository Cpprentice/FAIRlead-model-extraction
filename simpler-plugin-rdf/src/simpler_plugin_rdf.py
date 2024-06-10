import codecs
import collections
import shutil
from pathlib import Path
from tempfile import TemporaryFile, NamedTemporaryFile
from typing import List, Dict

from owlready2 import get_ontology, Ontology, ThingClass, World, sync_reasoner_pellet, EXACTLY, MAX, MIN
from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Graph, RDF, OWL, RDFS

from simpler_core.plugin import DataSourcePlugin, DataSourceType
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


class SparqlDataSourceType(DataSourceType):
    name = 'SPARQL'
    inputs = [
        'connector'
    ]


class OwlDataSourceType(DataSourceType):
    name = 'OWL'
    inputs = [
        'ontology',
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

        graph = Graph()
        world = World()
        # graph2 = Graph()
        # graph.parse(str(OWL))  # TODO find an offline solution

        with self.storage.get_data(name) as stream_lookup:
            if 'ontology' in stream_lookup:
                graph.parse(stream_lookup['ontology'])
                # stream_lookup['ontology'].seek(0)
                # graph2.parse(stream_lookup['ontology'])
                with NamedTemporaryFile('w', newline='', delete_on_close=False, encoding='utf-8') as stream:
                    stream_path_url = Path(stream.name).as_uri().replace('///', '//')
                    stream.write(graph.serialize(format='ntriples'))
                    stream.close()
                    ontology = world.get_ontology(stream_path_url).load()
            sync_reasoner_pellet(world)
            target_namespace = graph.namespace_manager.expand_curie(':')

            classes = sorted(build_iterative_class_list(ontology), key=lambda x: x.name)
            data_properties = sorted(ontology.data_properties(), key=lambda x: x.name)
            object_properties = sorted(ontology.object_properties(), key=lambda x: x.name)

            object_property_query = object_property_query_template.format(
                ' '.join(f'<{class_.iri}>' for class_ in classes),
                ' '.join(f'<{prop.iri}>' for prop in object_properties)
            )

            direct_instance_query = direct_instance_query_template.format(
                ' '.join(f'<{class_.iri}>' for class_ in classes)
            )

            property_restrictions = collections.defaultdict(list)
            for domain, restriction, prop in world.sparql(property_restrictions_query):
                if restriction.type in relevant_restrictions:
                    cardinality = str(restriction.cardinality) if restriction.cardinality is not None else 'n'
                    if restriction.type == EXACTLY:
                        property_restrictions[(domain, prop)].append([cardinality, cardinality])
                    elif restriction.type == MIN:
                        property_restrictions[(domain, prop)].append([cardinality, 'n'])
                    elif restriction.type == MAX:
                        property_restrictions[(domain, prop)].append(['0', cardinality])
                    else:
                        raise NotImplementedError('restriction type not supported')

            if any(len(l) != 1 for l in property_restrictions.values()):
                raise RuntimeError(
                    'restriction has multiple definitions for cardinality on the same domain / property pair')
            property_restrictions = {
                key: l[0]
                for key, l in property_restrictions.items()
            }

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

                ontology.imported_ontologies.append(data_ontology)
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
                url=f'http://localhost:7373/schemata/mondial-rdf/entities/{class_.name}',
                name=class_.name,
                type='strong',
                attributes=[],
                related_entities=[],
                key=None
            )

            attributes = []
            for data_prop in data_properties:
                if all(clause._satisfied_by(class_) for clause in data_prop.domain):
                    attribute = Attribute(
                        name=data_prop.name,
                        type=type_factory(data_prop.range),
                        is_collection=False,
                        is_key=False
                    )
                    attributes.append(attribute)
            entity.attributes = attributes

            relations = []
            for object_prop in object_properties:
                if all(clause._satisfied_by(class_) for clause in object_prop.domain):
                    for target_class in [
                        target_class
                        for target_class in classes
                        if all(clause._satisfied_by(target_class) for clause in object_prop.range)
                    ]:
                        if only_include_if_data_exists:
                            if (class_, object_prop, target_class) not in object_property_query_data:
                                continue
                            x = 42

                        entity_link = EntityLink(
                            name=target_class.name,
                            relation_name=object_prop.name,
                            cardinalities=
                            ['0', 'n']
                            if (class_, object_prop) not in property_restrictions
                            else property_restrictions[(class_, object_prop)],
                            link=f'http://localhost:7373/schemata/mondial-rdf/entities/{target_class.name}',
                        )
                        relations.append(entity_link)
            entity.related_entities = relations

            entities[entity.name].append(entity)
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
