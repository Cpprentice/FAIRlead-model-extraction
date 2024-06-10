import codecs
import collections
import functools
import itertools
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Dict, Set

from sqlalchemy import create_engine, Connection, text

from simpler_core.plugin import DataSourcePlugin, DataSourceType
from simpler_model import Attribute, EntityLink, Entity


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
    no: int
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


class SqlDataSourceType(DataSourceType):
    name = 'SQL'
    inputs = ['connector']


class SqlDataSourcePlugin(DataSourcePlugin):

    data_source_type = SqlDataSourceType()

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

            column_type = 'string'
            if any(x in column.data_type for x in ['int', 'serial']):
                column_type = 'int'
            elif any(x in column.data_type for x in ['real', 'double', 'numeric']):
                column_type = 'float'

            attribute_lookup[column.table_name].append(Attribute(
                name=column.column_name,
                type=column_type,
                is_collection=False,
                is_key=False  # TODO populate key state of column
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

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        with (self.get_sql_cursor(name) as cursor):

            table_names = self._get_table_names(cursor)
            foreign_key_objects = self._get_foreign_key_objects(cursor)
            filtered_foreign_key_objects = \
                self._get_foreign_keys_that_apply_to_determining_entity_weakness(foreign_key_objects)
            attribute_lookup = self._get_attribute_lookup(cursor)

            entities = []
            for table_name in table_names:
                name_set = set()
                short_name = table_name.replace('public.', '')
                relations = []

                for foreign_key in foreign_key_objects:
                    if foreign_key.primary_table == table_name:
                        fk_short_name = foreign_key.foreign_table.replace('public.', '')

                        if fk_short_name not in name_set:
                            name_set.add(fk_short_name)
                            relations.append(
                                EntityLink(
                                    name=fk_short_name,
                                    link=self.url_factory('get_entity_by_id', schemaId=name, entityId=fk_short_name)
                                )
                            )

                entities.append(Entity(
                    name=short_name,
                    url=self.url_factory('get_entity_by_id', schemaId=name, entityId=short_name),
                    type='strong' if not any(foreign_key.foreign_table == table_name for foreign_key in
                                             filtered_foreign_key_objects) else 'weak',
                    attributes=attribute_lookup[table_name],
                    key=None,
                    related_entities=relations
                ))
        return entities

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        all_entities = self.get_all_entities(name)
        for entity in all_entities:
            if entity.name == entity_id:
                return entity
        raise KeyError()
