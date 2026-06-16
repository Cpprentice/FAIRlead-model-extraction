import csv
import json
import re
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Callable, Dict, Iterable, TextIO, Any, ClassVar
from zipfile import ZipFile

from linkml_runtime.linkml_model import SchemaDefinition, ClassDefinition, SlotDefinition
from linkml_runtime.utils.schema_builder import SchemaBuilder
from openpyxl import load_workbook
import pandas as pd
import yaml
from openpyxl.cell import Cell
from openpyxl.worksheet.table import Table
from openpyxl.worksheet.worksheet import Worksheet
import pyarrow.parquet

from fairlead_core.plugin import DataSourcePlugin, DataSourceType, InputFlag
from fairlead_core.performance import profile
from fairlead_core.storage import ManualFilesystemDataSourceStorage
from simpler_model import Entity, Attribute
from simpler_plugin_json import JSONDataSourcePlugin


class TabularDataSourceType(DataSourceType):
    name = 'Tabular'
    inputs = [
        ('data_no_header', InputFlag.BINARY),  # A zip file containing all partial CSV files
        ('data_header', InputFlag.BINARY),     # A zip file containing all partial CSV files
        # 'schema'
    ]
    input_validation_statement = r'(data_header.*|data_no_header.*)'


def extract_csv_data(directory: Path, reader_factory: Callable[[TextIO, ...], Iterable], **kwargs) -> Dict:
    result = {}
    encoding = None
    if 'encoding' in kwargs:
        encoding = kwargs['encoding']
        del kwargs['encoding']  # TODO this breaks if we do need to call this method twice (some files with and some files without header)
    for file in directory.glob('*.csv'):
        with open(file, 'r', encoding=encoding) as stream:
            reader = reader_factory(stream, **kwargs)
            result[file.stem] = list(reader)
    return result


class TabularDataSourcePlugin(DataSourcePlugin):

    def get_schema(self, name: str) -> SchemaDefinition:
        builder = SchemaBuilder(name)
        csv_reader_args = self.storage.get_data_source_settings(name).get('csv_reader', {})

        no_header_data = None
        with_header_data = None
        with self.storage.get_data(name) as stream_lookup, \
                TemporaryDirectory() as zip_no_header_directory, \
                TemporaryDirectory() as zip_directory:
            if 'data_no_header' in stream_lookup:
                with ZipFile(stream_lookup['data_no_header']) as zip_handle:
                    zip_handle.extractall(zip_no_header_directory)
                no_header_data = extract_csv_data(Path(zip_no_header_directory), csv.reader, **csv_reader_args)
            if 'data_header' in stream_lookup:
                with ZipFile(stream_lookup['data_header']) as zip_handle:
                    zip_handle.extractall(zip_directory)
                with_header_data = extract_csv_data(Path(zip_directory),
                                                    lambda stream, **kwargs: csv.DictReader(stream, **kwargs),
                                                    **csv_reader_args)

        if with_header_data is None:
            with_header_data = {}
        if no_header_data is None:
            no_header_data = {}
        for key, table in no_header_data.items():
            with_header_data[key] = [
                {
                    f'Column{idx}': cell
                    for idx, cell in enumerate(row)
                }
                for row in table
            ]

        for entity_name, entity_data in with_header_data.items():
            attributes = []
            for rank, heading in enumerate(entity_data[0].keys()):
                combined_name = heading  # f'{entity_name}_{heading}'
                if combined_name == '' or combined_name is None:
                    combined_name = 'empty_column'
                attributes.append(SlotDefinition(
                    name=combined_name,
                    range='string',
                    rank=rank
                ))

            builder.add_class(ClassDefinition(
                name=entity_name,
                attributes=attributes
            ))
        return builder.schema

    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        return None, None

    data_source_type = TabularDataSourceType()

    def get_all_entities(self, name: str) -> List[Entity]:
        csv_reader_args = self.storage.get_data_source_settings(name)['csv_reader']

        no_header_data = None
        with_header_data = None
        schema = None
        with self.storage.get_data(name) as stream_lookup, \
                TemporaryDirectory() as zip_no_header_directory, \
                TemporaryDirectory() as zip_directory:
            if 'data_no_header' in stream_lookup:
                with ZipFile(stream_lookup['data_no_header']) as zip_handle:
                    zip_handle.extractall(zip_no_header_directory)
                no_header_data = extract_csv_data(Path(zip_no_header_directory), csv.reader, **csv_reader_args)
            if 'data_header' in stream_lookup:
                with ZipFile(stream_lookup['data_header']) as zip_handle:
                    zip_handle.extractall(zip_directory)
                with_header_data = extract_csv_data(Path(zip_directory), lambda stream, **kwargs: csv.DictReader(stream, **kwargs), **csv_reader_args)
            # if 'schema' in stream_lookup:
            #     schema_data = load_external_schema_from_yaml(stream_lookup['schema'])
            #     schema = {
            #         entity.entity_name[0]: entity
            #         for entity_data in schema_data
            #         for entity in [Entity.from_dict(entity_data)]
            #     }

        if with_header_data is None:
            with_header_data = {}
        if no_header_data is None:
            no_header_data = {}
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
                    combined_name = f'{entity_name}_{heading}'
                    attribute = Attribute(
                        attribute_name=[combined_name],
                        is_attribute_of=None,
                        has_attribute_modifier=[]
                    )
                    attributes.append(attribute)
                entity.has_attribute = attributes
                entities.append(entity)

        return entities

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass


def get_table_ref_without_header(table: Table) -> str:
    start, end = table.ref.split(':')
    column, row = re.match(r'([A-Z]*)(\d+)', start).groups()
    new_row = str(int(row) + table.headerRowCount)
    return f'{column}{new_row}:{end}'


def get_index_range_of_ref_string(ref: str) -> range:
    start, end = ref.split(':')
    _, start_row = re.match(r'([A-Z]*)(\d+)', start).groups()
    _, end_row = re.match(r'([A-Z]*)(\d+)', end).groups()

    return range(int(start_row), int(end_row) + 1)


# powered by MS copilot
def column_string_to_number(column_string):
    column_string = column_string.upper()
    column_number = 0
    for char in column_string:
        column_number = column_number * 26 + (ord(char) - ord('A') + 1)
    return column_number - 1


def get_column_count_from_data_ref(ref: str) -> int:
    start, end = ref.split(':')
    start_column, _ = re.match(r'([A-Z]+)(\d*)', start).groups()
    end_column, _ = re.match(r'([A-Z]+)(\d*)', end).groups()
    start_number = column_string_to_number(start_column)
    end_number = column_string_to_number(end_column)
    return end_number - start_number + 1


def data_generator(sheet: Worksheet, ref: str):
    start, end = ref.split(':')
    start_column, start_row = re.match(r'([A-Z]+)(\d+)', start).groups()
    end_column, end_row = re.match(r'([A-Z]+)(\d+)', end).groups()

    start_row_number = int(start_row)
    end_row_number = int(end_row)

    start_column_number = column_string_to_number(start_column) + 1
    end_column_number = column_string_to_number(end_column) + 1

    for row in sheet.iter_rows(
        min_row=start_row_number,
        max_row=end_row_number,
        min_col=start_column_number,
        max_col=end_column_number
    ):
        yield [cell.value for cell in row]

#
# @dataclass
# class ExcelCellReference:
#     numeric_column: int
#     row: int
#
#     splitter: ClassVar[re.Pattern] = re.compile(r'^([A-Z]+)(\d+)$', re.IGNORECASE)
#
#     @property
#     def column(self) -> str:
#         val = self.numeric_column
#         column = ''
#         while val >= 26:
#             column += 'A'
#             val -= 26
#         column += chr(ord('A') + val)
#         return column
#
#     def __str__(self) -> str:
#         return f'{self.column.upper()}{self.row}'
#
#     def __repr__(self) -> str:
#         return str(self)
#
#     @classmethod
#     def from_ref(cls, ref: str):
#         column, row = cls.splitter.match(ref).groups()
#         numeric_column = sum(ord(c) - ord('A') for c in column.upper())
#         return ExcelCellReference(numeric_column, int(row))
#
#     def shift_left(self) -> Self | None:
#         return self.shift_horizontal(-1)
#
#     def shift_right(self) -> Self | None:
#         return self.shift_horizontal(1)
#
#     def shift_up(self) -> Self | None:
#         return self.shift_vertical(-1)
#
#     def shift_down(self) -> Self | None:
#         return self.shift_vertical(1)
#
#     def shift_horizontal(self, distance: int) -> Self | None:
#         new_col = ord(self.column.upper()) + distance
#
#     def shift_vertical(self, distance: int) -> Self | None:
#         new_row = self.row + distance
#         if new_row <= 0:
#             return None
#         return ExcelCellReference(
#             column=self.column,
#             row=new_row,
#         )

@dataclass
class ExcelTableDefinition:
    index: pd.MultiIndex | pd.Index | List[int | str] | range
    columns: pd.MultiIndex | pd.Index | List[str]
    data_ref: str
    worksheet: Worksheet
    table_name: str

    default_table_name_check_regex: ClassVar[re.Pattern] = re.compile(r'(Table|Tabelle)\d+', re.IGNORECASE)

    def get_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            data=data_generator(self.worksheet, self.data_ref),
            index=self.index,
            columns=self.columns
        )

    # generated by copilot
    @staticmethod
    def sed_replace(expression: str, text: str) -> str:
        delim = expression[0]
        parts = re.split(rf'(?<!\\){delim}', expression)

        if len(parts) < 4:
            raise ValueError("Invalid sed expression")

        _, pattern, replacement, *_ = parts

        # Unescape the delimiter
        pattern = pattern.replace(f"\\{delim}", delim)
        replacement = replacement.replace(f"\\{delim}", delim)

        return re.sub(pattern, replacement, text)

    @staticmethod
    def improve_table_name(table: Table, worksheet: Worksheet, settings: dict[str, Any]) -> str:
        if ExcelTableDefinition.default_table_name_check_regex.match(table.name) is None:
            return table.name

        table_start_ref, _ = table.ref.split(':')
        column_string, row_index = re.match(r'^([A-Z]+)(\d+)$', table_start_ref, re.IGNORECASE).groups()
        row_index = int(row_index)
        column_index = column_string_to_number(column_string) + 1

        start_cell = worksheet.cell(row_index, int(column_index))

        def _get_cell(row_offset: int, column_offset: int) -> Cell | None:
            try:
                return start_cell.offset(row_offset, column_offset)
            except ValueError:
                return None

        neighbor_cells = [
            _get_cell(-1, 0),
            _get_cell(0, -1),
            _get_cell(-1, -1)
        ]

        new_name = None
        for cell in neighbor_cells:
            if cell is not None:
                new_name = str(cell.value)
                break
        if new_name is None:
            new_name = worksheet.title

        name_filter_regex = settings.get('table_name_filter_regex', None)
        if name_filter_regex is not None:
            return ExcelTableDefinition.sed_replace(name_filter_regex, new_name)

        return new_name

    @staticmethod
    def from_native_table(table: Table, worksheet: Worksheet, settings: dict[str, Any]) -> 'ExcelTableDefinition':
        data_ref = get_table_ref_without_header(table)
        return ExcelTableDefinition(
            index=get_index_range_of_ref_string(data_ref),
            columns=table.column_names,
            data_ref=data_ref,
            worksheet=worksheet,
            table_name=ExcelTableDefinition.improve_table_name(table, worksheet, settings)
        )

    @staticmethod
    def from_custom_table_def(
            worksheet: Worksheet,
            header_ref: str | None,
            data_ref: str,
            name: str
    ) -> 'ExcelTableDefinition':
        if header_ref is not None:
            column_data = list(data_generator(worksheet, header_ref))
            if len(column_data) == 1:
                columns = column_data[0]
            else:
                columns = pd.MultiIndex.from_arrays(column_data)
        else:
            columns = [
                f'Column{i}'
                for i in range(1, get_column_count_from_data_ref(data_ref) + 1)
            ]
        return ExcelTableDefinition(
            index=get_index_range_of_ref_string(data_ref),
            columns=columns,
            data_ref=data_ref,
            worksheet=worksheet,
            table_name=name
        )


class ExcelDataSourceType(DataSourceType):
    name = 'Excel'
    inputs = [
        ('workbook.xlsx', InputFlag.BINARY),  # The XLSX Document
        ('table_def.yaml', InputFlag.TEXT)
    ]
    input_validation_statement = r'.*workbook\.xlsx'


class ExcelDataSourcePlugin(DataSourcePlugin):

    def get_schema(self, name: str) -> SchemaDefinition:
        tables = self._get_tables(name)
        obj = {
            key: frame.to_dict(orient='records')
            for key, frame in tables.items()
        }
        return JSONDataSourcePlugin.generate_schema_from_dict(obj, name)


    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        pass

    data_source_type = ExcelDataSourceType()

    def _get_tables(self, name: str) -> Dict[str, pd.DataFrame]:
        settings = self.storage.get_data_source_settings(name)
        # TODO update this to factory style stream opening
        tables: Dict[str, pd.DataFrame] = {}
        table_definitions: List[ExcelTableDefinition] = []
        with self.storage.get_data(name) as stream_lookup:
            # workbook = load_workbook(stream_lookup['workbook.xlsx'], read_only=True)
            workbook = load_workbook(stream_lookup['workbook.xlsx'])
            # reader = pd.ExcelReader(stream_lookup['workbook.xlsx'])

            sheets = [workbook[name] for name in workbook.sheetnames]
            # native_tables = [table for sheet in sheets for table in sheet.tables.values()]
            table_definitions.extend([
                ExcelTableDefinition.from_native_table(
                    table,
                    sheet,
                    settings
                )
                for sheet in sheets
                for table in sheet.tables.values()
            ])

            if 'table_def.yaml' in stream_lookup:
                parsed_definitions = yaml.safe_load(stream_lookup['table_def.yaml'])
                table_definitions.extend([
                    ExcelTableDefinition.from_custom_table_def(
                        workbook[definition['sheet_name']],
                        definition['header_ref'],
                        definition['data_ref'],
                        definition['name']
                    )
                    for definition in parsed_definitions
                ])
            datetime_types = [
                'datetime64[ns]', # 'datetime64[ns,tz]',
                'datetime64[ms]', 'datetime64[s]',
                'datetime64[m]', 'datetime64[h]'
            ]
            for definition in table_definitions:
                frame = definition.get_frame()
                for col in frame.select_dtypes(include='datetime64').columns:
                    frame[col] = frame[col].apply(
                        lambda val: val.isoformat() if isinstance(val, pd.Timestamp) else val
                    ).astype('object').replace({pd.NaT: None})
                # force all object type columns to string to prevent any json incompatibilites
                for col in frame.select_dtypes(include='object').columns:
                    frame[col] = frame[col].astype(str)
                tables[definition.table_name] = frame

        return tables

    def get_all_entities(self, name: str) -> List[Entity]:
        tables = self._get_tables(name)
        obj = {
            key: frame.to_dict(orient='records')
            for key, frame in tables.items()
        }
        return JSONDataSourcePlugin.generate_model_from_dict(obj)

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass


class ParquetDataSourceType(DataSourceType):
    name = 'Parquet'
    inputs = [
        ('data', InputFlag.BINARY)
    ]
    input_validation_statement = r'data'


class ParquetDataSourcePlugin(DataSourcePlugin):

    # @staticmethod
    # @contextlib.contextmanager
    # def _zip_parquet_streams(raw_stream: io.BufferedReader) -> dict[str, io.BufferedReader]:
    #     with ZipFile(raw_stream) as zip_file:
    #         data = {}
    #         try:
    #             for file_name in zip_file.namelist():
    #                 if file_name.lower().endswith('.parquet'):
    #                     data[file_name] = zip_file.open(file_name, 'r')
    #
    #             yield data
    #         finally:
    #             for stream in data.values():
    #                 stream.close()

    # @staticmethod
    # @contextlib.contextmanager
    # def _extracted_parquet_streams(cache_dir: Path) -> dict[str, io.BufferedReader]:
    #     data = {}
    #     try:
    #         for file_name in cache_dir.glob('*.parquet'):
    #             data[file_name.name] = open(file_name, 'rb')
    #
    #         yield data
    #     finally:
    #         for stream in data.values():
    #             stream.close()

    @staticmethod
    @profile
    def ensure_zip_file_extracted(zip_file: ZipFile, cache_dir: Path):

        def _check_hash(target_path: Path) -> str:
            cache_memory_file = target_path.with_name(target_path.name + '.cache.json')
            if not cache_memory_file.exists():
                cache_memory: dict[str, Any] = {
                    'modified_time': None,
                    'hash': None
                }
            else:
                cache_memory = json.loads(cache_memory_file.read_text())

            modified_time = target_path.stat().st_mtime

            if cache_memory['modified_time'] is None or cache_memory['modified_time'] < modified_time:
                cache_memory['hash'] = ParquetDataSourcePlugin.crc32_file(target_path)
                cache_memory['modified_time'] = modified_time

            cache_memory_file.write_text(json.dumps(cache_memory))
            return cache_memory['hash']

        for info in zip_file.infolist():
            target_file = cache_dir / info.filename
            if target_file.exists() and target_file.is_file() and _check_hash(target_file) == info.CRC:
                continue
            zip_file.extract(info, cache_dir)
            if target_file.is_file():
                _check_hash(target_file)

    @staticmethod
    @profile
    def crc32_file(path, chunk_size=1024 * 1024):
        crc = 0
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                crc = zlib.crc32(chunk, crc)
        return crc & 0xffffffff  # normalize to unsigned 32-bit

    @profile
    def get_schema(self, name: str) -> SchemaDefinition:
        storage = self.storage
        schema_id = name
        with self.storage.get_data(name) as stream_lookup:
            parquet_stream = stream_lookup['data']
            if zipfile.is_zipfile(parquet_stream):
                with ZipFile(parquet_stream) as zip_file:
                    combined_cache_name = f"{name}.cache"
                    schema_id = combined_cache_name
                    cache_dir = self.storage.get_file_path(name, combined_cache_name)
                    self.ensure_zip_file_extracted(zip_file, cache_dir)
                    storage = ManualFilesystemDataSourceStorage(files={
                        combined_cache_name: (self.data_source_type.name, {
                            path.name: path
                            for path in cache_dir.rglob('*.parquet')
                        })
                    }, cache_path=cache_dir)
            else:
                storage = ManualFilesystemDataSourceStorage(files={
                    schema_id: (self.data_source_type.name, {
                        schema_id: self.storage.get_file_path(schema_id, schema_id)
                    })
                })
            # if self.is_zip_stream(parquet_stream):
            #     context_manager = self._zip_parquet_streams(parquet_stream)
            # else:
            #     context_manager = contextlib.nullcontext({'data': parquet_stream})
        stream_factory_lookup = storage.get_data_factory(schema_id)
        schema_builder = SchemaBuilder(name)
        for file_name, stream_factory in stream_factory_lookup['data'].items():

            file_path = Path(file_name)
            file_name_no_extension = file_path.stem

            parquet_file = pyarrow.parquet.ParquetFile(stream_factory())
            columns = parquet_file.schema.names
            attributes = []
            for rank, column in enumerate(columns):
                attributes.append(SlotDefinition(column, rank=rank))

            schema_builder.add_class(ClassDefinition(file_name_no_extension, attributes=attributes))
        return schema_builder.schema


    def get_all_entities(self, name: str) -> List[Entity]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass

    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        pass

    data_source_type = ParquetDataSourceType()

