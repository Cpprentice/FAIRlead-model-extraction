import codecs
import collections
import functools
import itertools
import json
import re
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import List, Dict, Set

from linkml_runtime.linkml_model import SchemaDefinition, SlotDefinition, ClassDefinition
from linkml_runtime.utils.schema_builder import SchemaBuilder
from sqlalchemy import create_engine, Connection, text, MetaData, ForeignKey as SqlForeignKey, Column as SqlColumn, \
    Table, select
from sqlalchemy.orm import declarative_base

from fairlead_core.cardinality import create_cardinality, merge_cardinalities
from fairlead_core.plugin import DataSourcePlugin, DataSourceType, InputFlag

try:
    from simpler_model import Attribute, Relation, Entity, EntityModifier, RelationModifier, AttributeModifier

    EntityLink = Relation
except ImportError:
    from simpler_model import Attribute, Entity, EntityLink

# the following should work not just for postgres
table_name_query = text("""
SELECT table_schema || '.' || table_name
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
AND table_schema NOT IN ('pg_catalog', 'information_schema');
""")

columns_query = text("""
SELECT
    table_schema || '.' || table_name as table_name,
    column_name,
    is_nullable = 'YES' as nullable,
    data_type
FROM
    information_schema.columns
WHERE
    table_schema NOT IN ('pg_catalog', 'information_schema')
""")


@dataclass
class Column:
    table_name: str
    column_name: str
    nullable: bool
    data_type: str


primary_key_query = text("""
select tab.table_schema || '.' || tab.table_name as table_name,
       tco.constraint_name,
       string_agg(kcu.column_name, ', ') as key_columns
from information_schema.tables tab
left join information_schema.table_constraints tco
          on tco.table_schema = tab.table_schema
          and tco.table_name = tab.table_name
          and tco.constraint_type = 'PRIMARY KEY'
left join information_schema.key_column_usage kcu 
          on kcu.constraint_name = tco.constraint_name
          and kcu.constraint_schema = tco.constraint_schema
          and kcu.constraint_name = tco.constraint_name
where tab.table_schema not in ('pg_catalog', 'information_schema')
      and tab.table_type = 'BASE TABLE'
group by tab.table_schema,
         tab.table_name,
         tco.constraint_name
order by tab.table_schema,
         tab.table_name;
""")


@dataclass(order=True, unsafe_hash=True)
class ForeignKey:
    foreign_table: str
    constraint_name: str
    fk_column: str
    nullable: bool
    no: int  # TODO remove this
    primary_table: str
    pk_column: str
    column_count: int = None

    @property
    def source(self) -> str:
        return f'{self.foreign_table}.{self.fk_column}'

    @property
    def target(self) -> str:
        return f'{self.primary_table}.{self.pk_column}'


foreign_key_query = text("""
select kcu.table_schema || '.' || kcu.table_name as foreign_table,
       kcu.constraint_name,
       kcu.column_name as fk_column,
       col.is_nullable = 'YES' as nullable,
       kcu.ordinal_position as no,
       rel_kcu.table_schema || '.' || rel_kcu.table_name as primary_table,
       rel_kcu.column_name as pk_column

from information_schema.table_constraints tco
join information_schema.key_column_usage kcu
          on tco.constraint_schema = kcu.constraint_schema
          and tco.constraint_name = kcu.constraint_name
          and tco.constraint_schema = 'public'
join information_schema.referential_constraints rco
          on tco.constraint_schema = rco.constraint_schema
          and tco.constraint_name = rco.constraint_name
join information_schema.key_column_usage rel_kcu
          on rco.unique_constraint_schema = rel_kcu.constraint_schema
          and rco.unique_constraint_name = rel_kcu.constraint_name
          and kcu.ordinal_position = rel_kcu.ordinal_position
join information_schema.columns col
    ON col.column_name = kcu.column_name
    AND col.table_name = tco.table_name
    AND col.table_schema = tco.table_schema
where tco.constraint_type = 'FOREIGN KEY'
order by kcu.table_schema,
         kcu.table_name,
         kcu.ordinal_position;
""")

unique_query = text("""
select kcu.table_schema || '.' || kcu.table_name as foreign_table,
       kcu.constraint_name,
       kcu.column_name as fk_column,
       col.is_nullable = 'YES' as nullable,
       kcu.ordinal_position as no

from information_schema.table_constraints tco
join information_schema.key_column_usage kcu
          on tco.constraint_schema = kcu.constraint_schema
          and tco.constraint_name = kcu.constraint_name
          and tco.constraint_schema = 'public'
join information_schema.columns col
    ON col.column_name = kcu.column_name
    AND col.table_name = tco.table_name
    AND col.table_schema = tco.table_schema
where tco.constraint_type = 'UNIQUE'
order by kcu.table_schema,
         kcu.table_name,
         kcu.ordinal_position;
""")


def to_snake_case(s: str) -> str:
    words = re.split(r'\s+', s.strip())
    return '_'.join(word.lower() for word in words if word)

def to_camel_case(s: str) -> str:
    words = re.split(r'\s+', s.strip())
    return ''.join(word.capitalize() for word in words if word)


class SqlDataSourceType(DataSourceType):
    name = 'SQL'
    inputs = [('connector', InputFlag.TEXT | InputFlag.SECURE)]


class SqliteDataSourceType(DataSourceType):
    name = 'Sqlite'
    inputs = [('database', InputFlag.BINARY)]


class BaseSqlDataSourcePlugin(DataSourcePlugin):
    data_source_type = None

    @abstractmethod
    @contextmanager
    def get_sql_cursor(self, name) -> Connection: ...

    def get_metadata(self, name: str) -> MetaData:
        base = declarative_base()
        metadata = base.metadata
        with self.get_sql_cursor(name) as cursor:
            metadata.reflect(cursor)
        return metadata

    @staticmethod
    def _get_table_names(metadata: MetaData) -> List[str]:
        return list(metadata.tables.keys())

    @staticmethod
    def _get_foreign_key_objects(metadata: MetaData) -> List[ForeignKey]:
        native_foreign_keys = sorted([
            fk
            for table in metadata.tables.values()
            for fk in table.foreign_keys
        ], key=str)
        # TODO it seems this call is non deterministic for the order and consecutive calls give another order
        #  lets try if sorted(key=str) does fix that

        # The following does only take each constraint once but maintains order
        #  However, just using the constraints seems to lose information - in the mini mondial we have 9 fk entries
        #  for the different columns but only a total of 4 constraints that address multiple columns.
        #  We must loop each constraint multiple times to find all columns
        constraint_list = list(dict.fromkeys(fk.constraint for fk in native_foreign_keys))
        # constraint_set = set(fk.constraint for fk in native_foreign_keys)
        constraint_name_lookup = {
            constraint: f'constraint_{num + 1}'
            # for num, constraint in enumerate(constraint_set)
            # for num, constraint in enumerate(fk.constraint for fk in native_foreign_keys)
            for num, constraint in enumerate(constraint_list)
        }
        fk_name_lookup = {
            fk: f'fk_{num + 1}'
            for num, fk in enumerate(native_foreign_keys)
        }

        foreign_keys = [
            ForeignKey(
                foreign_table=fk.parent.table.name,
                # constraint_name=fk.name if fk.name is not None else constraint_name_lookup[fk.constraint],
                constraint_name=fk.name if fk.name is not None else fk_name_lookup[fk],
                fk_column=fk.parent.name,
                nullable=fk.column.nullable,
                no=0,
                primary_table=fk.column.table.name,
                pk_column=fk.column.name,
                column_count=len(fk.constraint.columns)
            )
            for fk in native_foreign_keys
        ]
        return foreign_keys

    @staticmethod
    def _recurse_key_circles(column: str, lookup: Dict[str, List[str]], visited=None) -> List[List[str]]:
        if visited is None:
            visited = []

        if column in visited:
            return [[*visited, column]]
        visited.append(column)

        next_paths = []
        if column in lookup:
            next_columns = lookup[column]
            next_paths.extend([
                inner_path
                for next_column in next_columns
                for inner_path in BaseSqlDataSourcePlugin._recurse_key_circles(next_column, lookup, visited.copy())
            ])
        return next_paths

    @staticmethod
    def _determine_foreign_key_circles(foreign_keys: List[ForeignKey]) -> List[List[ForeignKey]]:
        relation_lookup = collections.defaultdict(list)

        # we take a step back to table/column pairs and their linking first to avoid
        #  n^2 iterations over all foreign keys
        for fk in foreign_keys:
            relation_lookup[fk.source].append(fk.target)

        paths: Dict[str, List[List[str]]] = {}  # these are the paths based on each table/column pair
        for key in relation_lookup.keys():
            paths[key] = BaseSqlDataSourcePlugin._recurse_key_circles(key, relation_lookup)

        visited = set()
        circles = []
        for path_list in paths.values():
            for path in path_list:
                circle_string = '->'.join(path[path.index(path[-1]):])
                if circle_string not in visited:
                    visited.add(circle_string)
                    circles.append(path[path.index(path[-1]):])

        circle_fk_objs = []
        for circle in circles:
            fk_chain = []
            for from_path, to_path in itertools.pairwise(circle):
                from_table, from_column = from_path.rsplit('.', maxsplit=1)
                to_table, to_column = to_path.rsplit('.', maxsplit=1)

                applicable_foreign_key = list(filter(
                    lambda x: x.foreign_table == from_table and x.fk_column == from_column and
                              x.primary_table == to_table and x.pk_column == to_column,
                    foreign_keys
                ))[0]
                fk_chain.append(applicable_foreign_key)

            circle_fk_objs.append(fk_chain)
        return circle_fk_objs

    @staticmethod
    def _get_attribute_lookup(metadata: MetaData) -> Dict[str, List[Attribute]]:

        # result = cursor.execute(columns_query)
        attribute_lookup = collections.defaultdict(list)

        for table in metadata.tables.values():
            for column in table.columns:
                attribute_lookup[column.table.name].append(Attribute(
                    attribute_name=[column.name],
                    has_attribute_modifier=[AttributeModifier(attribute_modifier='key')]
                        if column.primary_key or (not column.nullable and column.unique)
                        else None,
                    # TODO Should we consider unique constraints as well <- we do if they are not nullable
                    #  however for the sqlite db of sincal it seems the unique flag is None even for unique columns
                ))
        return attribute_lookup

    @staticmethod
    def _get_linkml_attribute_lookup(metadata: MetaData) -> dict[str, list[SlotDefinition]]:
        attribute_lookup = collections.defaultdict(list)

        for table in metadata.tables.values():


            table_index_lookup = collections.defaultdict(lambda: False)
            for index in table.indexes:
                for column in index.columns:
                    table_index_lookup[column.name] = True


            for rank, column in enumerate(table.columns):
                attribute_lookup[column.table.name].append(SlotDefinition(
                    name=column.name,
                    identifier=column.primary_key or (not column.nullable and column.unique) or
                        column.index is not None or table_index_lookup[column.name] or None,
                    required=not column.nullable,
                    range=column.type,
                    rank=rank
                    # TODO Should we consider unique constraints as well <- we do if they are not nullable
                    #  however for the sqlite db of sincal it seems the unique flag is None even for unique columns
                ))
        return attribute_lookup

    @staticmethod
    def _get_foreign_keys_that_apply_to_determining_entity_weakness(foreign_keys: List[ForeignKey]) -> List[ForeignKey]:
        ignorable_fks: Set[ForeignKey] = set()

        # Handle foreign key circles
        foreign_key_chains = BaseSqlDataSourcePlugin._determine_foreign_key_circles(foreign_keys)
        for circle in foreign_key_chains:
            highest_column_count_fk: ForeignKey | None = functools.reduce(
                lambda acc, x: x if acc is None or x.column_count > acc.column_count else acc,
                circle,
                None
            )
            ignorable_fks.add(highest_column_count_fk)

        filtered_foreign_key_objects = []
        for a in foreign_keys:
            found = False
            for b in ignorable_fks:
                if a.constraint_name == b.constraint_name:
                    found = True
                    break
            if not found and a.nullable is False:
                filtered_foreign_key_objects.append(a)

        return filtered_foreign_key_objects

    def get_schema(self, name: str) -> SchemaDefinition:
        builder = SchemaBuilder(name)
        builder.add_defaults()
        metadata = self.get_metadata(name)
        with (self.get_sql_cursor(name) as cursor):

            table_names = self._get_table_names(metadata)
            foreign_key_objects = self._get_foreign_key_objects(metadata)
            filtered_foreign_key_objects = \
                self._get_foreign_keys_that_apply_to_determining_entity_weakness(foreign_key_objects)
            attribute_lookup = self._get_linkml_attribute_lookup(metadata)

            grouped_foreign_keys = collections.defaultdict(list)
            for f_key in filtered_foreign_key_objects:
                grouped_foreign_keys[f_key.constraint_name].append(f_key)

            cardinalities = {
                (fk.source, fk.target): (0, 1) if any(x.nullable for x in group) else (1, 1)
                for constraint_name, group in grouped_foreign_keys.items()
                for fk in group
            }
            added_transitives = {1}
            while added_transitives:
                added_transitives = set()
                for (source, target), cardinality in cardinalities.items():
                    for (inner_source, inner_target), inner_cardinality in cardinalities.items():
                        if target == inner_source and (source, inner_target) not in cardinalities:
                            added_transitives.add((
                                (source, inner_target),
                                merge_cardinalities(cardinality, inner_cardinality)
                            ))
                for key, value in added_transitives:
                    cardinalities[key] = value
            grouped_cardinalities = collections.defaultdict(list)
            for (source, target), cardinality in cardinalities.items():
                source_table_name, _ = source.rsplit('.', maxsplit=1)
                target_table_name, _ = target.rsplit('.', maxsplit=1)
                grouped_cardinalities[(source_table_name, target_table_name)].append(cardinality)
            cardinality_implications = {
                key: functools.reduce(merge_cardinalities, cardinality_list, cardinality_list[0])
                for key, cardinality_list in grouped_cardinalities.items()
            }

            # entities = []
            for table_name in table_names:
                name_set = set()
                short_name = table_name.replace('public.', '')
                # relations = []
                relation_slot_names = []

                for foreign_key in foreign_key_objects:
                    slot_name = to_snake_case(foreign_key.constraint_name)
                    alias = None
                    if slot_name != foreign_key.constraint_name:
                        alias = foreign_key.constraint_name

                    # if foreign_key.primary_table == table_name:
                    if foreign_key.foreign_table == table_name:
                        # fk_short_name = foreign_key.foreign_table.replace('public.', '')
                        fk_short_name = foreign_key.primary_table.replace('public.', '')

                        if fk_short_name not in name_set:
                            name_set.add(fk_short_name)

                            subject_cardinality = create_cardinality((0, sys.maxsize))
                            if (foreign_key.primary_table, table_name) in cardinality_implications:
                                subject_cardinality = create_cardinality(
                                    cardinality_implications[(foreign_key.primary_table, table_name)])

                            builder.add_slot(SlotDefinition(
                                name=slot_name,
                                alias=alias,
                                range=fk_short_name,
                                domain=short_name,
                                required=not foreign_key.nullable,
                                # TODO think about something for an identifying relation
                                # identifier=foreign_key in filtered_foreign_key_objects or None
                            ))
                            relation_slot_names.append(slot_name)
                            # relations.append(
                            #     Relation(
                            #         relation_name=[foreign_key.constraint_name],
                            #         has_object_entity=fk_short_name,
                            #         has_subject_entity=short_name,
                            #         object_cardinality=create_cardinality((0, 1) if
                            #                                               foreign_key.nullable else (1, 1)),
                            #         subject_cardinality=subject_cardinality,
                            #         has_attribute=[],
                            #         has_relation_modifier=[RelationModifier(relation_modifier='identifying')]
                            #         if foreign_key in filtered_foreign_key_objects else None
                            #     )
                            # )
                is_weak = any(foreign_key.foreign_table == table_name for foreign_key in filtered_foreign_key_objects)
                # is_weak = any(foreign_key.primary_table == table_name for foreign_key in filtered_foreign_key_objects)
                builder.add_class(ClassDefinition(
                    name=short_name,
                    attributes=attribute_lookup[table_name],
                    slots=relation_slot_names,  # this should auto encode weakness if any of the slots is an identifier
                ))
                # entities.append(Entity(
                #     entity_name=[short_name],
                #     has_attribute=attribute_lookup[table_name],
                #     has_entity_modifier=None if not is_weak else [EntityModifier(entity_modifier='weak')],
                #     is_object_in_relation=[],
                #     is_subject_in_relation=relations
                # ))
        return builder.schema

    def get_all_entities(self, name: str) -> List[Entity]:
        metadata = self.get_metadata(name)
        with (self.get_sql_cursor(name) as cursor):

            table_names = self._get_table_names(metadata)
            foreign_key_objects = self._get_foreign_key_objects(metadata)
            filtered_foreign_key_objects = \
                self._get_foreign_keys_that_apply_to_determining_entity_weakness(foreign_key_objects)
            attribute_lookup = self._get_attribute_lookup(metadata)

            grouped_foreign_keys = collections.defaultdict(list)
            for f_key in filtered_foreign_key_objects:
                grouped_foreign_keys[f_key.constraint_name].append(f_key)

            cardinalities = {
                (fk.source, fk.target): (0, 1) if any(x.nullable for x in group) else (1, 1)
                for constraint_name, group in grouped_foreign_keys.items()
                for fk in group
            }
            added_transitives = {1}
            while added_transitives:
                added_transitives = set()
                for (source, target), cardinality in cardinalities.items():
                    for (inner_source, inner_target), inner_cardinality in cardinalities.items():
                        if target == inner_source and (source, inner_target) not in cardinalities:
                            added_transitives.add((
                                (source, inner_target),
                                merge_cardinalities(cardinality, inner_cardinality)
                            ))
                for key, value in added_transitives:
                    cardinalities[key] = value
            grouped_cardinalities = collections.defaultdict(list)
            for (source, target), cardinality in cardinalities.items():
                source_table_name, _ = source.rsplit('.', maxsplit=1)
                target_table_name, _ = target.rsplit('.', maxsplit=1)
                grouped_cardinalities[(source_table_name, target_table_name)].append(cardinality)
            cardinality_implications = {
                key: functools.reduce(merge_cardinalities, cardinality_list, cardinality_list[0])
                for key, cardinality_list in grouped_cardinalities.items()
            }

            entities = []
            for table_name in table_names:
                name_set = set()
                short_name = table_name.replace('public.', '')
                relations = []

                for foreign_key in foreign_key_objects:
                    # if foreign_key.primary_table == table_name:
                    if foreign_key.foreign_table == table_name:
                        # fk_short_name = foreign_key.foreign_table.replace('public.', '')
                        fk_short_name = foreign_key.primary_table.replace('public.', '')

                        if fk_short_name not in name_set:
                            name_set.add(fk_short_name)

                            subject_cardinality = create_cardinality((0, sys.maxsize))
                            if (foreign_key.primary_table, table_name) in cardinality_implications:
                                subject_cardinality = create_cardinality(
                                    cardinality_implications[(foreign_key.primary_table, table_name)])

                            relations.append(
                                Relation(
                                    relation_name=[foreign_key.constraint_name],
                                    has_object_entity=fk_short_name,
                                    has_subject_entity=short_name,
                                    object_cardinality=create_cardinality((0, 1) if
                                                                          foreign_key.nullable else (1, 1)),
                                    subject_cardinality=subject_cardinality,
                                    has_attribute=[],
                                    has_relation_modifier=[RelationModifier(relation_modifier='identifying')]
                                    if foreign_key in filtered_foreign_key_objects else None
                                )
                            )
                is_weak = any(foreign_key.foreign_table == table_name for foreign_key in filtered_foreign_key_objects)
                # is_weak = any(foreign_key.primary_table == table_name for foreign_key in filtered_foreign_key_objects)
                entities.append(Entity(
                    entity_name=[short_name],
                    has_attribute=attribute_lookup[table_name],
                    has_entity_modifier=None if not is_weak else [EntityModifier(entity_modifier='weak')],
                    is_object_in_relation=[],
                    is_subject_in_relation=relations
                ))
        return entities

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        all_entities = self.get_all_entities(name)
        for entity in all_entities:
            if entity.name == entity_id:
                return entity
        raise KeyError()

    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        # entity = self.get_entity_by_id(name, entity_id)  # this fails if there is no such entity
        metadata = self.get_metadata(name)
        with (self.get_sql_cursor(name) as cursor):
            table: Table = metadata.tables[entity_id]
            statement = select(table)
            result = cursor.execute(statement)
            return json.dumps(result).encode('utf-8'), 'application/json'


class SqliteDataSourcePlugin(BaseSqlDataSourcePlugin):
    data_source_type = SqliteDataSourceType()

    @contextmanager
    def get_sql_cursor(self, name: str) -> Connection:
        engine = create_engine(f'sqlite{self.storage.get_file_path(name, 'database').absolute().as_uri()[4:]}')
        with engine.connect() as cursor:
            yield cursor


class SqlDataSourcePlugin(BaseSqlDataSourcePlugin):
    @contextmanager
    def get_sql_cursor(self, name) -> Connection:
        with self.storage.get_data(name) as data_lookup:
            connector_stream = codecs.getreader('utf-8')(data_lookup['connector'])
            connector_string = connector_stream.read()
        engine = create_engine(connector_string)
        with engine.connect() as cursor:
            yield cursor

    data_source_type = SqlDataSourceType()


class OldSqlDataSourcePlugin(DataSourcePlugin):

    data_source_type = None  # SimpleNamespace(name='deprecated')

    @contextmanager
    def get_sql_cursor(self, name: str) -> Connection:
        with self.storage.get_data(name) as data_lookup:
            connector_stream = codecs.getreader('utf-8')(data_lookup['connector'])
            connector_string = connector_stream.read()
        engine = create_engine(connector_string)
        with engine.connect() as cursor:
            yield cursor

    @staticmethod
    def _get_table_names(cursor: Connection) -> List[str]:
        result = cursor.execute(table_name_query)
        return [x[0] for x in result]

    @staticmethod
    def _get_foreign_key_objects(cursor: Connection) -> List[ForeignKey]:
        result = cursor.execute(foreign_key_query)
        foreign_keys = [ForeignKey(**x._mapping) for x in result]

        # Perform post-processing to add the column count of the constraint to each foreign key.
        #  In the future we could also think about adding this to the query but that makes the query more complex
        grouped_foreign_keys = collections.defaultdict(list)
        for fk in foreign_keys:
            grouped_foreign_keys[fk.constraint_name].append(fk)
        for group in grouped_foreign_keys.values():
            column_count = max(x.no for x in group)
            for fk in group:
                fk.column_count = column_count

        return foreign_keys

    @staticmethod
    def _recurse_key_circles(column: str, lookup: Dict[str, List[str]], visited=None) -> List[List[str]]:
        if visited is None:
            visited = []

        if column in visited:
            return [[*visited, column]]
        visited.append(column)

        next_paths = []
        if column in lookup:
            next_columns = lookup[column]
            next_paths.extend([
                inner_path
                for next_column in next_columns
                for inner_path in SqlDataSourcePlugin._recurse_key_circles(next_column, lookup, visited.copy())
            ])
        return next_paths

    @staticmethod
    def _determine_foreign_key_circles(foreign_keys: List[ForeignKey]) -> List[List[ForeignKey]]:
        relation_lookup = collections.defaultdict(list)

        # we take a step back to table/column pairs and their linking first to avoid
        #  n^2 iterations over all foreign keys
        for fk in foreign_keys:
            relation_lookup[fk.source].append(fk.target)

        paths: Dict[str, List[List[str]]] = {}  # these are the paths based on each table/column pair
        for key in relation_lookup.keys():
            paths[key] = SqlDataSourcePlugin._recurse_key_circles(key, relation_lookup)

        visited = set()
        circles = []
        for path_list in paths.values():
            for path in path_list:
                circle_string = '->'.join(path[path.index(path[-1]):])
                if circle_string not in visited:
                    visited.add(circle_string)
                    circles.append(path[path.index(path[-1]):])

        circle_fk_objs = []
        for circle in circles:
            fk_chain = []
            for from_path, to_path in itertools.pairwise(circle):
                from_table, from_column = from_path.rsplit('.', maxsplit=1)
                to_table, to_column = to_path.rsplit('.', maxsplit=1)

                applicable_foreign_key = list(filter(
                    lambda x: x.foreign_table == from_table and x.fk_column == from_column and
                              x.primary_table == to_table and x.pk_column == to_column,
                    foreign_keys
                ))[0]
                fk_chain.append(applicable_foreign_key)

            circle_fk_objs.append(fk_chain)
        return circle_fk_objs

    @staticmethod
    def _get_attribute_lookup(cursor: Connection) -> Dict[str, List[Attribute]]:
        result = cursor.execute(columns_query)
        attribute_lookup = collections.defaultdict(list)
        for row in result:
            column = Column(**row._mapping)

            # column_type = 'string'
            # if any(x in column.data_type for x in ['int', 'serial']):
            #     column_type = 'int'
            # elif any(x in column.data_type for x in ['real', 'double', 'numeric']):
            #     column_type = 'float'

            attribute_lookup[column.table_name].append(Attribute(
                attribute_name=[column.column_name],
                has_attribute_modifier=None  # TODO populate key state of column
            ))
        return attribute_lookup

    @staticmethod
    def _get_foreign_keys_that_apply_to_determining_entity_weakness(foreign_keys: List[ForeignKey]) -> List[ForeignKey]:
        ignorable_fks: Set[ForeignKey] = set()

        # Handle foreign key circles
        foreign_key_chains = SqlDataSourcePlugin._determine_foreign_key_circles(foreign_keys)
        for circle in foreign_key_chains:
            highest_column_count_fk = functools.reduce(
                lambda acc, x: x if acc is None or x.column_count > acc.column_count else acc,
                circle,
                None
            )
            ignorable_fks.add(highest_column_count_fk)

        filtered_foreign_key_objects = []
        for a in foreign_keys:
            found = False
            for b in ignorable_fks:
                if a.constraint_name == b.constraint_name:
                    found = True
                    break
            if not found and a.nullable == False:
                filtered_foreign_key_objects.append(a)

        return filtered_foreign_key_objects

    def get_all_entities(self, name: str) -> List[Entity]:
        with (self.get_sql_cursor(name) as cursor):

            table_names = self._get_table_names(cursor)
            foreign_key_objects = self._get_foreign_key_objects(cursor)
            filtered_foreign_key_objects = \
                self._get_foreign_keys_that_apply_to_determining_entity_weakness(foreign_key_objects)
            attribute_lookup = self._get_attribute_lookup(cursor)

            grouped_foreign_keys = collections.defaultdict(list)
            for f_key in filtered_foreign_key_objects:
                grouped_foreign_keys[f_key.constraint_name].append(f_key)

            cardinalities = {
                (fk.source, fk.target): (0, 1) if any(x.nullable for x in group) else (1, 1)
                for constraint_name, group in grouped_foreign_keys.items()
                for fk in group
            }
            added_transitives = {1}
            while added_transitives:
                added_transitives = set()
                for (source, target), cardinality in cardinalities.items():
                    for (inner_source, inner_target), inner_cardinality in cardinalities.items():
                        if target == inner_source and (source, inner_target) not in cardinalities:
                            added_transitives.add((
                                (source, inner_target),
                                merge_cardinalities(cardinality, inner_cardinality)
                            ))
                for key, value in added_transitives:
                    cardinalities[key] = value
            grouped_cardinalities = collections.defaultdict(list)
            for (source, target), cardinality in cardinalities.items():
                source_table_name, _ = source.rsplit('.', maxsplit=1)
                target_table_name, _ = target.rsplit('.', maxsplit=1)
                grouped_cardinalities[(source_table_name, target_table_name)].append(cardinality)
            cardinality_implications = {
                key: functools.reduce(merge_cardinalities, cardinality_list, cardinality_list[0])
                for key, cardinality_list in grouped_cardinalities.items()
            }

            entities = []
            for table_name in table_names:
                name_set = set()
                short_name = table_name.replace('public.', '')
                relations = []

                for foreign_key in foreign_key_objects:
                    # if foreign_key.primary_table == table_name:
                    if foreign_key.foreign_table == table_name:
                        # fk_short_name = foreign_key.foreign_table.replace('public.', '')
                        fk_short_name = foreign_key.primary_table.replace('public.', '')

                        if fk_short_name not in name_set:
                            name_set.add(fk_short_name)

                            subject_cardinality = create_cardinality((0, sys.maxsize))
                            if (foreign_key.primary_table, table_name) in cardinality_implications:
                                subject_cardinality = create_cardinality(
                                    cardinality_implications[(foreign_key.primary_table, table_name)])

                            relations.append(
                                Relation(
                                    relation_name=[foreign_key.constraint_name],
                                    has_object_entity=fk_short_name,
                                    has_subject_entity=short_name,
                                    object_cardinality=create_cardinality((0, 1) if
                                                                          foreign_key.nullable else (1, 1)),
                                    subject_cardinality=subject_cardinality,
                                    has_attribute=[],
                                    has_relation_modifier=[RelationModifier(relation_modifier='identifying')]
                                        if foreign_key in filtered_foreign_key_objects else None
                                )
                            )
                is_weak = any(foreign_key.foreign_table == table_name for foreign_key in filtered_foreign_key_objects)
                # is_weak = any(foreign_key.primary_table == table_name for foreign_key in filtered_foreign_key_objects)
                entities.append(Entity(
                    entity_name=[short_name],
                    has_attribute=attribute_lookup[table_name],
                    has_entity_modifier=None if not is_weak else [EntityModifier(entity_modifier='weak')],
                    is_object_in_relation=[],
                    is_subject_in_relation=relations
                ))
        return entities

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        all_entities = self.get_all_entities(name)
        for entity in all_entities:
            if entity.name == entity_id:
                return entity
        raise KeyError()


def cardinality_maker(foreign_key: ForeignKey) -> List[str]:
    if foreign_key.nullable:
        return ['0..1', 'n']
    return ['1', 'n']
