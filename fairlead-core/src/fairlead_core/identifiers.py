import collections
import json
import uuid
from abc import ABC, abstractmethod
from functools import cache
from pathlib import Path
from typing import Protocol, Any, Self

import yaml
from curies import Converter

# from fairlead_core.storage import DataSourceStorage


# class IdentifierHandlingStrategyProtocol(Protocol):
#     def resolve(self, entity: Any) -> tuple[bool, str]:
#         """Resolve an entity towards a local identifier and a boolean whether this is globally unique"""
#
#
# class IdentifierHandlingStrategy:
#     _lookup: dict[str, type[Self]] = {}
#
#     def __init_subclass__(cls, **kwargs):
#         IdentifierHandlingStrategy._lookup[cls.__name__] = cls
#
#     @staticmethod
#     def factory(name: str, *args, **kwargs):
#         return IdentifierHandlingStrategy._lookup[name](*args, **kwargs)
#
#
# class GloballyUniqueAttribute(IdentifierHandlingStrategy):
#     def __init__(self, attribute_name: str):
#         self.attribute_name = attribute_name
#
#     def resolve(self, entity: Any) -> tuple[bool, str]:
#         return True, entity[self.attribute_name]
#
#
# class LocallyUniqueAttribute(IdentifierHandlingStrategy):
#     def __init__(self, attribute_name: str):
#         self.attribute_name = attribute_name
#
#     def resolve(self, entity: Any) -> tuple[bool, str]:
#         return False, entity[self.attribute_name]
#
#
# class LocallyUniqueValueSet(IdentifierHandlingStrategy):
#     def __init__(self, attribute_name_set: set[str]):
#         self.attribute_names = attribute_name_set
#
#     def resolve(self, entity: Any) -> tuple[bool, str]:
#         hashed_value = ss
#         return False, str(hashed_value)


class IdentifierStorageService(ABC):
    # def __init__(self, file_storage_service: DataSourceStorage):
    def __init__(self):
        # self.file_storage_service = file_storage_service
        # self.data_sources: dict[str, dict[str, IdentifierHandlingStrategyProtocol]] = collections.defaultdict(dict)
        self.prefix_map: dict[str, str] = {
            'DOI': 'https://doi.org/'
        }
        self.converter = Converter.from_prefix_map(self.prefix_map)

    # @property
    # def data_sources(self) -> dict[str, dict[str, IdentifierHandlingStrategyProtocol]]:
    #     sources = collections.defaultdict(dict)
    #     for data_source_name in self.file_storage_service.list_available_data():
    #         settings = self.file_storage_service.get_data_source_settings(data_source_name)
    #         sources[data_source_name] = {
    #             key: IdentifierHandlingStrategy.factory(strategy_name, *args)
    #             for key, [strategy_name, *args] in settings['id_strategy'].items()
    #         }
    #     return sources

    def add_prefix(self, prefix: str, url: str):
        self.prefix_map[prefix] = url
        self.converter = Converter.from_prefix_map(self.prefix_map)

    # def add_data_source_and_entity_strategy(self, name: str, entity_name: str, strategy: IdentifierHandlingStrategyProtocol):
    #     self.data_sources[name][entity_name] = strategy

    # def get_id(self, entity: Any, data_source_name: str, entity_name: str) -> str:
        # strategy = self.data_sources[data_source_name][entity_name]  # TODO update the strategies to rather work with lists/tuples of values that can be assembled in RML
        # is_globally_unique, resolved_id = strategy.resolve(entity)
        # if is_globally_unique:
        #     return self.converter.compress(resolved_id)
        # return self.get_guid(data_source_name, entity_name, resolved_id)

    def compress_url(self, url: str) -> str:
        return self.converter.compress(url)

    @abstractmethod
    def get_guid(self, data_source: str, entity_name: str, local_id: str) -> str:
        ...

    # TODO we should add an abstractmethod that allows reverse querying from unique id -> fields that where used to hash


class YamlFileIdentifierStorage(IdentifierStorageService):

    # def __init__(self, path: Path, storage: DataSourceStorage):
    def __init__(self, path: Path):
        # super().__init__(storage)
        super().__init__()
        self.path = path

    @cache
    def _storage(self) -> dict[tuple[str, str, str], str]:
        if not self.path.is_file():
            return {}
        with open(self.path, 'r') as stream:
            return yaml.unsafe_load(stream)  # TODO search for alternative storage schema such that we do not use tuples

    def get_guid(self, data_source: str, entity_name: str, local_id: str) -> str:
        storage = self._storage()
        try:
            return storage[data_source, entity_name, local_id]
        except KeyError:
            new_guid = str(uuid.uuid4())
            storage[data_source, entity_name, local_id] = new_guid
            with open(self.path, 'w') as stream:
                yaml.dump(storage, stream)  # TODO return to safe_dump once new schema is established
            self._storage.cache_clear()
            return new_guid
