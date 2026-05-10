import collections
import hashlib
import io
import json
import shelve
from pathlib import Path
from typing import List
import urllib.request
import urllib.response

from jsonpath import JSONPath
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView
from doi_meta_retriever import resolve_core_data, FileFetcher, FileRecord

from fairlead_core.plugin import DataSourceType, InputFlag, DataSourcePlugin, EntityLink
from fairlead_core.storage import ManualFilesystemDataSourceStorage
from fairlead_core.performance import profile
from simpler_model import Entity



def md5_of_file(path: Path, chunk_size: int = 8192) -> str:
    md5 = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5.update(chunk)
    return md5.hexdigest()


class DOIDataSourceType(DataSourceType):
    name = 'DOI'
    inputs = [
        ('doi', InputFlag.TEXT | InputFlag.SHOW_IN_JSON)
    ]
    input_validation_statement = r'doi'


class DOIDataSourcePlugin(DataSourcePlugin):
    data_source_type = DOIDataSourceType()

    @profile
    def _cache_files(self, name:str, files: list[FileRecord]):

        def _download_file(target_path: Path, from_url: str):
            with urllib.request.urlopen(from_url) as response:
                target_path.write_bytes(response.read())

        def _check_hash(target_path: Path) -> str:
            cache_memory_file = target_path.with_name(target_path.name + '.cache.json')
            if not cache_memory_file.exists():
                cache_memory = {
                    'modified_time': None,
                    'hash': None
                }
            else:
                cache_memory = json.loads(cache_memory_file.read_text())

            modified_time = target_path.stat().st_mtime

            if cache_memory['modified_time'] is None or cache_memory['modified_time'] < modified_time:
                cache_memory['hash'] = md5_of_file(target_path)
                cache_memory['modified_time'] = modified_time

            cache_memory_file.write_text(json.dumps(cache_memory))
            return cache_memory['hash']

        with self.storage.get_data(name) as stream_lookup:
            for file in files:
                cache_file_path = self.storage.get_file_path(name, file.key)
                if file.key not in stream_lookup:
                    _download_file(cache_file_path, file.url)
                    _check_hash(cache_file_path)
                else:
                    local_hash = _check_hash(cache_file_path)
                    hash_algorithm, hash_value = file.checksum.split(':')
                    if hash_algorithm.lower() == 'md5':
                        if hash_value.lower() != local_hash.lower():
                            _download_file(cache_file_path, file.url)
                            _check_hash(cache_file_path)
                    else:
                        raise NotImplementedError('Only MD5 for hash checks implemented')

    @staticmethod
    def _build_file_config(file: FileRecord, plugin_type: str, cache_file_path: Path) -> tuple[str, dict[str, Path]]:
        if plugin_type == 'Parquet':
            return plugin_type, {
                'data': cache_file_path
            }
        # elif plugin_type == 'Tabular':
        #     return plugin_type, {
        #         ''
        #     }
        raise RuntimeError('Unsupported nested plugin type')

    @profile
    def get_schema(self, name: str) -> SchemaDefinition:
        with self.storage.get_data(name) as stream_lookup:
            doi = io.TextIOWrapper(stream_lookup['doi'], encoding='utf-8').read()
        settings = self.storage.get_data_source_settings(name)

        doi_cache = {}
        use_shelf = settings.get('use_shelf', False)
        if use_shelf:
            doi_cache = shelve.open(self.storage.get_file_path(name, 'doi.cache'))

        if 'doi_core_data' in doi_cache:
            doi_core_data = doi_cache['doi_core_data']
        else:
            doi_core_data = resolve_core_data(doi)
            doi_cache['doi_core_data'] = doi_core_data

        if 'files' in doi_cache:
            files = doi_cache['files']
        else:
            files = FileFetcher.factory(doi_core_data).fetch()
            doi_cache['files'] = files

        if use_shelf:
            doi_cache.close()

        self._cache_files(name, files)

        settings = self.storage.get_data_source_settings(name)
        file_settings = settings['file_settings']

        nested_storage = ManualFilesystemDataSourceStorage({
            file.key: self._build_file_config(file, file_settings[file.key], self.storage.get_file_path(name, file.key))
            for file in files
            if file.key in file_settings
        }, cache_path=self.storage.get_file_path(name, '.'))
        schema = SchemaDefinition(f'{name}Schema', id=f'{name}Id')
        view = SchemaView(schema)
        for file in files:
            if file.key in file_settings:
                target_plugin_name = file_settings[file.key]
                class_ = DataSourcePlugin.get_plugin_class(target_plugin_name)
                inner_plugin = class_(nested_storage)
                inner_schema = inner_plugin.get_schema(file.key)
                view.merge_schema(inner_schema)

        return view.schema

    def get_all_entities(self, name: str) -> List[Entity]:
        return []

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass

    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        return None, ''  # result_data, mime_type
