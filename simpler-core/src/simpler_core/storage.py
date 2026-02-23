from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
import shutil
from typing import Dict, IO, List, Tuple, Any

import yaml


class DataSourceStorage(ABC):
    """
    Abstract base class for all potential storage systems to be used by the UI
    """

    @contextmanager
    @abstractmethod
    def get_data(self, name: str) -> Dict[str, IO]:
        ...

    @abstractmethod
    def insert_data(self, name: str, plugin_name: str, parts: Dict[str, IO]):
        ...

    @abstractmethod
    def add_more_data(self, name: str, parts: dict[str, IO]): ...

    @abstractmethod
    def get_plugin_name(self, data_source_name: str) -> str:
        ...

    @abstractmethod
    def list_available_data(self) -> List[str]:
        ...

    @abstractmethod
    def get_file_path(self, data_source_name: str, part_name: str) -> Path:
        ...

    @abstractmethod
    def get_data_source_settings(self, data_source_name: str) -> dict[str, Any]:
        ...


class ManualFilesystemDataSourceStorage(DataSourceStorage):

    def __init__(self, files: Dict[str, Tuple[str, Dict[str, Path]]]):
        self.files = files

    @contextmanager
    def get_data(self, name: str) -> Dict[str, IO]:
        data = {}
        try:
            for input_name, file_path in self.files[name][1].items():
                data[input_name] = file_path.open('rb')
            yield data
        finally:
            for stream in data.values():
                stream.close()

    def insert_data(self, name: str, plugin_name: str, parts: Dict[str, IO]):
        raise NotImplementedError()

    def add_more_data(self, name: str, parts: dict[str, IO]):
        raise NotImplementedError()

    def get_plugin_name(self, data_source_name: str) -> str:
        return self.files[data_source_name][0]

    def list_available_data(self) -> List[str]:
        return list(self.files.keys())

    def get_file_path(self, data_source_name: str, part_name: str) -> Path:
        return self.files[data_source_name][1][part_name]

    def get_data_source_settings(self, data_source_name: str) -> dict[str, Any]:
        return {}


class FilesystemDataSourceStorage(DataSourceStorage):

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)

    def list_available_data(self) -> List[str]:
        return [x.parent.stem for x in self.storage_path.glob('*/plugin.yaml')]

    def insert_data(self, name: str, plugin_name: str, parts: Dict[str, IO]):
        new_path = self.storage_path / name
        new_path.mkdir(exist_ok=True)
        plugin_settings_file_path = self.storage_path / name / 'plugin.yaml'

        plugin_settings_file_path.write_text(yaml.safe_dump({
            'plugin_name': plugin_name,
            'id_strategy': {}
        }))
        for part_name, part_stream in parts.items():
            file_path = new_path / part_name
            with file_path.open('wb') as target_stream:
                shutil.copyfileobj(part_stream, target_stream)

    def add_more_data(self, name: str, parts: dict[str, IO]):
        data_path = self.storage_path / name
        for part_name, part_stream in parts.items():
            file_path = data_path / part_name
            with file_path.open('wb') as target_stream:
                shutil.copyfileobj(part_stream, target_stream)

    @contextmanager
    def get_data(self, name: str) -> Dict[str, IO]:

        read_directory_path = self.storage_path / name
        if not read_directory_path.is_dir():
            return {}
        data = {}
        try:
            for file_path in read_directory_path.iterdir():
                if file_path.is_file():
                    data[file_path.name] = file_path.open('rb')

            yield data
        finally:
            for stream in data.values():
                stream.close()

    def get_plugin_name(self, data_source_name: str) -> str:
        plugin_data = self.get_data_source_settings(data_source_name)
        return plugin_data['plugin_name']

    def get_file_path(self, data_source_name: str, part_name: str) -> Path:
        return self.storage_path / data_source_name / part_name

    def get_data_source_settings(self, data_source_name: str) -> dict[str, Any]:
        plugin_file_path = self.storage_path / data_source_name / 'plugin.yaml'
        with open(plugin_file_path, 'r') as stream:
            return yaml.safe_load(stream)
