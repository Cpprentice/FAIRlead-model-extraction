from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
import shutil
from typing import Dict, IO, List, Tuple


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
    def get_plugin_name(self, data_source_name: str) -> str:
        ...

    @abstractmethod
    def list_available_data(self) -> List[str]:
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

    def get_plugin_name(self, data_source_name: str) -> str:
        return self.files[data_source_name][0]

    def list_available_data(self) -> List[str]:
        return list(self.files.keys())


class FilesystemDataSourceStorage(DataSourceStorage):

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)

    def list_available_data(self) -> List[str]:
        return [x.stem for x in self.storage_path.glob('*.plugin')]

    def insert_data(self, name: str, plugin_name: str, parts: Dict[str, IO]):
        new_path = self.storage_path / name
        new_path.mkdir()
        plugin_file_path = self.storage_path / f'{name}.plugin'
        plugin_file_path.write_text(plugin_name)
        for part_name, part_stream in parts.items():
            file_path = new_path / part_name
            with file_path.open('w') as target_stream:
                shutil.copyfileobj(part_stream, target_stream)

    @contextmanager
    def get_data(self, name: str) -> Dict[str, IO]:

        read_directory_path = self.storage_path / name
        if not read_directory_path.is_dir():
            return {}
        data = {}
        try:
            for file_path in read_directory_path.iterdir():
                data[file_path.name] = file_path.open('rb')

            yield data
        finally:
            for stream in data.values():
                stream.close()

    def get_plugin_name(self, data_source_name: str) -> str:
        plugin_file_path = self.storage_path / f'{data_source_name}.plugin'
        return plugin_file_path.read_text()
