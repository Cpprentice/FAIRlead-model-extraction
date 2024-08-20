from typing import List
import urllib.parse

from pydot import Dot, Node, Edge

from simpler_model import Entity, EntityModifier, RelationModifier, Cardinality, Attribute

cardinality_translation = {
    'exactlyOne': '1',
    'any': 'n',
    'oneOrNone': '0..1',
    'oneOrMore': '1..n',
    'unsupported': '?'
}


def url_to_name(url: str) -> str:
    url_data = urllib.parse.urlparse(url)
    path_data = url_data.path.rpartition('/')
    return path_data[-1]


def create_graph(entities: List[Entity], show_attributes=False) -> Dot:
    graph = Dot(f'ER-Diagram', graph_type='graph')
    graph.set_fontname("Helvetica,Arial,sans-serif")
    graph.add_node(Node('node', fontname='Helvetica,Arial,sans-serif'))
    graph.add_node(Node('edge', fontname='Helvetica,Arial,sans-serif'))

    def entity_border_count(entity_modifiers: List[EntityModifier]) -> int:
        if entity_modifiers is not None:
            for modifier in entity_modifiers:
                if modifier.entity_modifier == 'weak':
                    return 2
        return 1

    def relation_border_count(relation_modifiers: List[RelationModifier]) -> int:
        if relation_modifiers is not None:
            for modifier in relation_modifiers:
                if modifier.relation_modifier == 'identifying':
                    return 2
        return 1

    def attribute_label(attr: Attribute) -> str:
        label = attribute.attribute_name[0]
        if attr.has_attribute_modifier is not None:
            for modifier in attr.has_attribute_modifier:
                if modifier.attribute_modifier == 'key':
                    return f'<<u>{label}</u>>'
        return label

    def cardinality_converter(cardinality: Cardinality) -> str:
        return cardinality_translation[cardinality.cardinality]

    entity_name_translation = {
        name: entity.entity_name[0]
        for entity in entities
        # if len(entity.entity_name) > 1
        for name in entity.entity_name[1:]
    }

    def translate_name(name: str) -> str:
        if name in entity_name_translation:
            return entity_name_translation[name]
        return name

    for entity in entities:
        entity_name = entity.entity_name[0]
        graph.add_node(Node(entity_name, shape='box', peripheries=entity_border_count(entity.has_entity_modifier)))

        if entity.is_subject_in_relation is not None:
            for relation in entity.is_subject_in_relation:
                relation_name = relation.relation_name[0]
                # related_entity_name = translate_name(url_to_name(relation.has_object_entity))
                related_entity_name = translate_name(relation.has_object_entity)
                sorted_relative_names = sorted([entity_name, related_entity_name])
                relation_id = f'#{relation_name}#'.join(sorted_relative_names)
                graph.add_node(Node(relation_id, label=relation_name,
                                    shape='diamond', fillcolor='lightgrey', style='filled',
                                    peripheries=relation_border_count(relation.has_relation_modifier)))
                graph.add_edge(Edge(entity_name, relation_id,
                                    label=cardinality_converter(relation.subject_cardinality)))
                graph.add_edge(Edge(related_entity_name, relation_id,
                                    label=cardinality_converter(relation.object_cardinality)))
        if show_attributes:
            if entity.has_attribute is not None:
                for attribute in entity.has_attribute:
                    attribute_name = attribute.attribute_name[0]
                    attribute_id = f'{entity_name}#{attribute_name}'
                    graph.add_node(Node(attribute_id, label=attribute_label(attribute), shape='ellipse'))
                    graph.add_edge(Edge(entity_name, attribute_id))
    return graph
