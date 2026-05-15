import collections
import functools
import math
from types import SimpleNamespace

import networkx as nx
from linkml_runtime import SchemaView
from linkml_runtime.linkml_model import SchemaDefinition, ClassDefinition
from linkml_runtime.utils.schema_builder import SchemaBuilder

from simpler_model import Entity, Partition


def _merge_small_sub_graphs(small_sub_graphs: list[nx.Graph], target_partition_size: int) -> list[nx.Graph]:
    target_graphs = []
    total_nodes_in_small_sub_graphs = functools.reduce(
        lambda acc, sub_graph: acc + sub_graph.number_of_nodes(),
        small_sub_graphs,
        0
    )
    partition_count = math.ceil(total_nodes_in_small_sub_graphs / target_partition_size)
    partition_size = math.ceil(total_nodes_in_small_sub_graphs / partition_count)

    small_sub_graphs_usage_lookup = [
        SimpleNamespace(used=False, graph=sub_graph)
        for sub_graph in small_sub_graphs
    ]
    for misc_partition_index in range(partition_count):
        node_count = 0
        target_graph = nx.Graph()
        for item in small_sub_graphs_usage_lookup:
            if not item.used:
                if item.graph.number_of_nodes() + node_count <= partition_size:
                    item.used = True
                    target_graph = nx.compose(target_graph, item.graph)
                    node_count += item.graph.number_of_nodes()
        target_graphs.append(target_graph)
    target_graphs.sort(key=len, reverse=True)
    for item in small_sub_graphs_usage_lookup:
        if not item.used:
            target_graphs[-1] = nx.compose(target_graphs[-1], item.graph)
            target_graphs.sort(key=len, reverse=True)
    return target_graphs


def _partition_entity_graph(graph: nx.Graph, target_partition_size: int, small_graph_size_limit: int) -> list[nx.Graph]:
    small_sub_graphs: list[nx.Graph] = []
    medium_sub_graphs: list[nx.Graph] = []
    large_sub_graphs: list[nx.Graph] = []
    for c in sorted(nx.connected_components(graph), key=len, reverse=True):
        sub_graph = graph.subgraph(c).copy()
        if sub_graph.number_of_nodes() <= small_graph_size_limit:
            small_sub_graphs.append(sub_graph)
        elif small_graph_size_limit < sub_graph.number_of_nodes() <= target_partition_size:
            medium_sub_graphs.append(sub_graph)
        else:
            large_sub_graphs.append(sub_graph)

    target_graphs = _merge_small_sub_graphs(small_sub_graphs, target_partition_size)
    target_graphs.extend(medium_sub_graphs)

    for sub_graph in large_sub_graphs:
        largest_degree_node = max(sub_graph.degree, key=lambda x: x[1])[0]
        largest_degree_node_neighbors = set(sub_graph.neighbors(largest_degree_node))
        sub_graph.remove_node(largest_degree_node)
        inner_graphs = _partition_entity_graph(sub_graph, target_partition_size - 1, small_graph_size_limit)
        for inner_graph in inner_graphs:
            if any(node in largest_degree_node_neighbors for node in inner_graph.nodes):
                relevant_nodes = set(inner_graph.nodes) & largest_degree_node_neighbors
                inner_graph.add_node(largest_degree_node)
                inner_graph.add_edges_from([(largest_degree_node, node) for node in relevant_nodes])
        target_graphs.extend(inner_graphs)
    return target_graphs


def create_partitioned_entity_list(
        entities: list[Entity],
        small_partition_limit=5,
        target_partition_size=25
) -> list[Partition]:
    graph, entity_lookup = create_nx_graph_from_entity_list(entities)
    nx_partitions = _partition_entity_graph(graph, target_partition_size, small_partition_limit)
    return [
        Partition(
            title=f'Partition {idx + 1}',
            entities=[
                entity_lookup[name]
                for name in sorted(partition.nodes)
            ]
        )
        for idx, partition in enumerate(nx_partitions)
    ]


def create_filtered_class_list(schema: SchemaDefinition, start_nodes: list[str], max_distance: int) -> SchemaDefinition:
    graph = create_nx_graph_from_schema(schema)
    reduced_graph = filter_nx_graph(graph, start_nodes, max_distance)
    sv = SchemaView(schema)
    builder = SchemaBuilder(name=f'{sv.schema.name}_filtered', id=f'{sv.schema.id}_filtered')


    for type_ in sv.all_types().values():
        builder.add_type(type_)

    for enum in sv.all_enums().values():
        builder.add_enum(enum)

    for slot in sv.all_slots(attributes=False).values():
        builder.add_slot(slot)

    for x in sorted(reduced_graph.nodes):
        builder.add_class(sv.get_class(x))
    return builder.schema

    to_visit_classes = set(start_nodes)
    classes = set()
    slots = set()
    types = set()
    enums = set()

    while to_visit_classes:
        c = to_visit_classes.pop()
        if c in classes:
            continue

        classes.add(c)

        # inheritance closure
        to_visit_classes.update(sv.class_parents(c))
        to_visit_classes.update(sv.class_children(c))

        # slots
        for s in sv.class_slots(c):
            slots.add(s)
            rng = sv.get_slot(s).range

            if rng in sv.all_classes():
                to_visit_classes.add(rng)
            elif rng in sv.all_types():
                types.add(rng)
            elif rng in sv.all_enums():
                enums.add(rng)

    for type_name in types:
        builder.add_type(sv.get_type(type_name))
    for enum_name in enums:
        builder.add_enum(sv.get_enum(enum_name))
    for class_name in classes:
        builder.add_class(sv.get_class(class_name))
    for slot_name in slots:
        builder.add_slot(sv.get_slot(slot_name))

    return builder.schema


def create_nx_graph_from_schema(schema: SchemaDefinition) -> nx.Graph:
    view = SchemaView(schema)
    g = nx.Graph()
    for class_name, class_ in view.all_classes().items():  # change ordering?
        g.add_node(class_name)
    g.add_edges_from([
        (class_name, view.induced_slot(slot_name, class_name).range)
        for class_name, class_ in view.all_classes().items()
        for slot_name in view.class_slots(class_name, attributes=False)
        # for slot in view.class_induced_slots(class_name)

    ])
    return g


def create_filtered_entity_list(entities: list[Entity], start_nodes: list[str], max_distance: int) -> list[Entity]:
    graph, entity_lookup = create_nx_graph_from_entity_list(entities)
    reduced_graph = filter_nx_graph(graph, start_nodes, max_distance)
    return [
        entity_lookup[x]
        for x in sorted(reduced_graph.nodes)
    ]


def filter_nx_graph(nxg: nx.Graph, start_nodes: list[str], max_distance: int) -> nx.Graph | None:
    nodes_within_distance = set()
    for start_node in start_nodes:
        try:
            nodes_within_distance.update(nx.single_source_shortest_path_length(nxg, start_node, cutoff=max_distance))
        except KeyError:
            return None

    reduced_graph = nxg.subgraph(nodes_within_distance)
    return reduced_graph


def create_nx_graph_from_entity_list(entities: list[Entity]) -> tuple[nx.Graph, dict[str, Entity]]:
    sorted_entities = sorted(entities, key=lambda x: x.entity_name[0])
    entity_lookup = {
        entity.entity_name[0]: entity
        for entity in sorted_entities
    }
    g = nx.Graph()
    for entity in sorted_entities:
        g.add_node(entity.entity_name[0], size=len(entity.is_subject_in_relation) + len(entity.has_attribute))
    g.add_edges_from([
        (entity.entity_name[0], relation.has_object_entity)
        for entity in sorted_entities
        for relation in entity.is_subject_in_relation
    ])
    return g, entity_lookup
    return nx.Graph(
        {
            entity.entity_name[0]: [
                entity_lookup[relation.has_object_entity].entity_name[0]
                for relation in entity.is_subject_in_relation
            ]
            for entity in sorted(entities, key=lambda x: x.entity_name[0])
        }
    ), entity_lookup


    sub_graphs = [
        graph.subgraph(c).copy()
        for c in sorted(nx.connected_components(graph), key=len, reverse=True)
    ]

    small_sub_graphs = [
        sub_graph
        for sub_graph in sub_graphs
        if sub_graph.number_of_nodes() <= small_graph_node_limit
    ]
    total_nodes_in_small_sub_graphs = functools.reduce(
        lambda acc, sub_graph: acc + sub_graph.number_of_nodes(),
        small_sub_graphs,
        0
    )
    misc_partition_count = math.ceil(total_nodes_in_small_sub_graphs / target_partition_size)
    misc_partition_size = math.ceil(total_nodes_in_small_sub_graphs / misc_partition_count)

    small_sub_graphs_usage_lookup = [
        SimpleNamespace(used=False, graph=sub_graph)
        for sub_graph in small_sub_graphs
    ]
    for misc_partition_index in range(misc_partition_count):
        node_count = 0
        target_graph = nx.Graph()
        for item in small_sub_graphs_usage_lookup:
            if not item.used:
                if item.graph.number_of_nodes() + node_count <= misc_partition_size:
                    item.used = True
                    target_graph = nx.compose(target_graph, item.graph)
                    node_count += item.graph.number_of_nodes()
        target_graphs.append(target_graph)

    medium_sub_graphs = [
        graph
        for graph in sub_graphs
        if small_graph_node_limit < graph.number_of_nodes() <= target_partition_size
    ]
    target_graphs.extend(medium_sub_graphs)

    large_sub_graphs = [
        graph
        for graph in sub_graphs
        if target_partition_size < graph.number_of_nodes()
    ]
    for graph in large_sub_graphs:
        graph_copy = graph.copy()
        # name_to_degree = sorted([
        #     (node, degree)
        #     for node, degree in graph.degree
        # ], key=lambda x: x[1], reverse=True)
        node_degrees = dict(graph_copy.degree())
        top_nodes = sorted(node_degrees, key=node_degrees.get, reverse=True)[:super_node_count]
        graph_copy.remove_nodes_from(top_nodes)

        inner_sub_graphs = [
            graph_copy.subgraph(c).copy()
            for c in sorted(nx.connected_components(graph_copy), key=len, reverse=True)
        ]



    _ = 42

