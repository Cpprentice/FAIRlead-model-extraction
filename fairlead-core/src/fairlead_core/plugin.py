import io
from abc import abstractmethod, ABC, ABCMeta
import re
from dataclasses import dataclass
from enum import IntFlag
from typing import ClassVar, List, Tuple, Type, Dict, Callable, Self, Any

from linkml_runtime.linkml_model import SchemaDefinition
from pydantic import BaseModel, Field

from fairlead_core.schema import apply_schema_correction_if_available, optimize_schema, introduce_inverse_relations, \
    get_user_schema_correction, multi_merge, load_schema_enhancement, apply_schema_enhancement
from fairlead_core.settings import OptimizationSettings
from fairlead_core.storage import DataSourceStorage
try:
    from simpler_model import Entity, Relation, SchemaEnhancement

    EntityLink = Relation
except ImportError:
    from simpler_model import Entity, EntityLink


class DataSourceTypeMeta(type):
    def __new__(cls, name, bases, attrs):
        if 'name' not in attrs:
            raise TypeError('The name attribute must be defined on all DataSourceType child classes')
        if 'inputs' not in attrs:
            raise TypeError('The inputs attribute must be defined on all DataSourceType child classes')
        return super().__new__(cls, name, bases, attrs)


class DataSourceTypeInputFlag(IntFlag):
    BINARY = 0
    TEXT = 1
    SECURE = 2
    SHOW_IN_JSON = 4

    def __str__(self) -> str:
        return self.name
        # is_binary = not (self.value & 1)
        # binary_prefix = 'BINARY|' if is_binary else ''
        # return f'{binary_prefix}{self.name}'


InputFlag = DataSourceTypeInputFlag


class DataSourceType(metaclass=DataSourceTypeMeta):
    name: str = None
    inputs: List[tuple[str, int]] = []
    input_validation_statement: str = None

    def validate_inputs(self, input_names: List[str]) -> bool:  # For now this is not reflecting the "inputs" type
        if self.input_validation_statement is None:
            return True
        input_name_string = ','.join(sorted(input_names))
        return re.match(f'^{self.input_validation_statement}$', input_name_string) is not None


del DataSourceType.name
del DataSourceType.inputs


# TODO shouldn't the following be actually placed into other packages as well - to the code that actually handles the
#  data source type? - So we could flexibly add new types as well
# class SQLDataSourceType(DataSourceType):
#     pass


# class XMLDataSourceType(DataSourceType):
#     pass


# TODO we need a metaclass for each datasource plugin to enforce the child classes to define the implementation_name
#  class attribute so we can make sure to get a list of available classes - the alternative is to have a cached lookup
#  that is being built on first access to a certain plugin
class DataSourcePluginMeta(type):
    def __new__(cls, name, bases, attrs):
        if 'data_source_type' not in attrs:
            raise TypeError('data_source_type attribute must be defined on all DataSourcePlugin child classes')
        return super().__new__(cls, name, bases, attrs)


class AbstractDataSourcePluginMeta(DataSourcePluginMeta, ABCMeta):
    """
    This is to satisfy Python to have a strict hierarchy of Metaclasses
    """


class DataSourcePlugin(ABC, metaclass=AbstractDataSourcePluginMeta):
    subclasses: Dict[str, type['DataSourcePlugin']] = {}

    data_source_type: DataSourceType = None

    def __init__(self, storage: DataSourceStorage):  # url_factory: Callable[[str, ...], str]
        self.storage = storage
        # self.url_factory = url_factory

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.data_source_type is not None:
            DataSourcePlugin.subclasses[cls.data_source_type.name] = cls

    @abstractmethod
    def get_schema(self, name: str) -> SchemaDefinition:
        ...

    @abstractmethod
    def get_all_entities(self, name: str) -> List[Entity]:
        ...

    @abstractmethod
    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        ...

    @abstractmethod
    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        ...

    @classmethod
    def get_data_source_types(cls) -> List[DataSourceType]:
        return [plugin_class.data_source_type for plugin_class in cls.subclasses.values()]

    @classmethod
    def get_plugin_class(cls, ds_type_string: str) -> type['DataSourcePlugin']:
        return cls.subclasses.get(ds_type_string)

    def get_cursor(self, name: str, optimization_settings: OptimizationSettings | None = None) -> 'DataSourceCursor':
        return DataSourceCursor(self, name, optimization_settings)

    # @classmethod
    # def entities(cls, type: DataSourceType) -> List[Entity]:
    #     cls.subclasses
    

del DataSourcePlugin.data_source_type


class DataSourceCursor:
    def __init__(self, plugin: DataSourcePlugin, name: str, optimization_settings: OptimizationSettings | None = None):
        self.plugin = plugin
        self.name = name
        self.settings = OptimizationSettings() if optimization_settings is None else optimization_settings

    def load_schema_enhancement(self) -> SchemaEnhancement:
        return load_schema_enhancement(self.plugin.storage, self.name)

    def get_schema(self) -> SchemaDefinition:
        schema = self.plugin.get_schema(self.name)
        if not self.settings.prevent_enhancement:
            schema_enhancement = self.load_schema_enhancement()
            schema = apply_schema_enhancement(schema, schema_enhancement, self.settings)

            if self.settings.generate_inverse_relations:
                # TODO introduce_inverse_relations(schema)
                pass
        return schema

    def get_all_entities(self) -> List[Entity]:
        entities = self.plugin.get_all_entities(self.name)
        if not self.settings.prevent_optimization:
            if not self.settings.prevent_user_optimization:
                user_pre_modded_entities = apply_schema_correction_if_available(entities, self.plugin.storage, self.name)

                if not self.settings.prevent_automatic_optimization:
                    original_copy = entities.copy()
                    pre_modded_copy = user_pre_modded_entities.copy()
                    optimize_schema(original_copy)
                    optimize_schema(pre_modded_copy)
                    user_mods = get_user_schema_correction(self.name, self.plugin.storage)
                    entities = multi_merge([entities, user_pre_modded_entities, original_copy, pre_modded_copy, user_mods])

                else:
                    entities = user_pre_modded_entities
            elif not self.settings.prevent_automatic_optimization:
                optimize_schema(entities)
            if self.settings.generate_inverse_relations:
                introduce_inverse_relations(entities)
        return entities

    def get_entity_by_id(self, entity_id: str):
        return self.plugin.get_entity_by_id(self.name, entity_id)

    def get_raw_data_by_entity(self, entity_id: str) -> tuple[bytes, str]:
        return self.plugin.get_raw_data_by_entity(self.name, entity_id)


class InputDataError(Exception):
    """Raised when the data does not match the given schema, or is otherwise malformatted"""


class AccessorPlugin(ABC):
    _subclass_registry: dict[str, type[Self]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._subclass_registry[cls.__name__[:-14]] = cls

    def __init__(self, storage: DataSourceStorage):
        self.meta_storage = storage

    @abstractmethod
    def get_artifact_metadata(self, schema_id: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_binary_resource_stream(self, schema_id: str, artifact_id: str) -> io.BufferedReader:
        ...
