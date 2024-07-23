import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Callable, Dict, Iterable, TextIO
from zipfile import ZipFile

from simpler_core.plugin import DataSourcePlugin, DataSourceType
from simpler_core.schema import load_external_schema_from_yaml
from simpler_model import Entity, Relation, Attribute


class TabularDataSourceType(DataSourceType):
    name = 'Tabular'
    inputs = [
        'data_no_header',  # A zip file containing all partial CSV files
        'data_header',     # A zip file containing all partial CSV files
        'schema'
    ]
    input_validation_statement = r'(data_header.*|data_no_header.*)'


def extract_csv_data(directory: Path, reader_factory: Callable[[TextIO], Iterable]) -> Dict:
    result = {}
    for file in directory.glob('*.csv'):
        with open(file, 'r') as stream:
            reader = reader_factory(stream)
            result[file.stem] = list(reader)
    return result


class TabularDataSourcePlugin(DataSourcePlugin):

    data_source_type = TabularDataSourceType()

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        no_header_data = None
        with_header_data = None
        schema = None
        with self.storage.get_data(name) as stream_lookup, \
                TemporaryDirectory() as zip_no_header_directory, \
                TemporaryDirectory() as zip_directory:
            if 'data_no_header' in stream_lookup:
                with ZipFile(stream_lookup['data_no_header']) as zip_handle:
                    zip_handle.extractall(zip_no_header_directory)
                no_header_data = extract_csv_data(Path(zip_no_header_directory), csv.reader)
            if 'data_header' in stream_lookup:
                with ZipFile(stream_lookup['data_header']) as zip_handle:
                    zip_handle.extractall(zip_directory)
                with_header_data = extract_csv_data(Path(zip_directory), lambda stream: csv.DictReader(stream))
            if 'schema' in stream_lookup:
                schema_data = load_external_schema_from_yaml(stream_lookup['schema'])
                schema = {
                    entity.entity_name[0]: entity
                    for entity_data in schema_data
                    for entity in [Entity.from_dict(entity_data)]
                }

        if with_header_data is None:
            with_header_data = {}
        for key, table in no_header_data.items():
            with_header_data[key] = [
                {
                    f'Column{idx}': cell
                    for idx, cell in enumerate(row)
                }
                for row in table
            ]

        entities = []
        for entity_name, entity_data in with_header_data.items():
            if schema is not None and entity_name in schema:
                entities.append(schema[entity_name])
            elif schema is None:
                entity = Entity(
                    has_attribute=[],
                    has_entity_modifier=[],
                    is_object_in_relation=[],
                    is_subject_in_relation=[],
                    entity_name=[entity_name]
                )
                attributes = []
                for heading in entity_data[0].keys():
                    attribute = Attribute(
                        attribute_name=[heading],
                        is_attribute_of=None,
                        has_attribute_modifier=[]
                    )
                    attributes.append(attribute)
                entity.has_attribute = attributes
                entities.append(entity)

        return entities

    def get_related_entity_links(self, name: str) -> List[Relation]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass
