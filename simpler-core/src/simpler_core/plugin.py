from abc import abstractmethod, ABC, ABCMeta
import re
from dataclasses import dataclass
from typing import ClassVar, List, Tuple, Type, Dict, Callable

from pydantic import BaseModel, Field

from simpler_core.schema import apply_schema_correction_if_available, optimize_schema, introduce_inverse_relations
from simpler_core.storage import DataSourceStorage
try:
    from simpler_model import Entity, Relation
    EntityLink = Relation
except ImportError:
    from simpler_model import Entity, EntityLink


class OptimizationSettings(BaseModel):
    prevent_optimization: bool = Field(False, alias='preventOptimization')
    prevent_automatic_optimization: bool = Field(False, alias='preventAutomaticOptimization')
    generate_inverse_relations: bool = Field(False, alias='generateInverseRelations')


class DataSourceTypeMeta(type):
    def __new__(cls, name, bases, attrs):
        if 'name' not in attrs:
            raise TypeError('The name attribute must be defined on all DataSourceType child classes')
        if 'inputs' not in attrs:
            raise TypeError('The inputs attribute must be defined on all DataSourceType child classes')
        return super().__new__(cls, name, bases, attrs)


class DataSourceType(metaclass=DataSourceTypeMeta):
    name: str = None
    inputs: List[str] = []
    input_validation_statement: str = None

    def validate_inputs(self, input_names: List[str]) -> bool:
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
    subclasses: Dict[str, Type] = {}

    data_source_type: DataSourceType = None

    def __init__(self, storage: DataSourceStorage, url_factory: Callable[[str, ...], str]):
        self.storage = storage
        self.url_factory = url_factory

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        DataSourcePlugin.subclasses[cls.data_source_type.name] = cls

    @abstractmethod
    def get_strong_entities(self, name: str) -> List[Entity]:
        ...

    @abstractmethod
    def get_all_entities(self, name: str) -> List[Entity]:
        ...

    @abstractmethod
    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        ...

    @abstractmethod
    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        ...

    @classmethod
    def get_data_source_types(cls) -> List[DataSourceType]:
        return [plugin_class.data_source_type for plugin_class in cls.subclasses.values()]

    @classmethod
    def get_plugin_class(cls, ds_type_string: str) -> Type:
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

    def get_strong_entities(self) -> List[Entity]:
        return self.plugin.get_strong_entities(self.name)

    def get_all_entities(self) -> List[Entity]:
        entities = self.plugin.get_all_entities(self.name)
        if not self.settings.prevent_optimization:
            entities = apply_schema_correction_if_available(entities, self.plugin.storage, self.name)
            if not self.settings.prevent_automatic_optimization:
                optimize_schema(entities)
            if self.settings.generate_inverse_relations:
                introduce_inverse_relations(entities)
        return entities

    def get_related_entity_links(self):
        return self.plugin.get_related_entity_links(self.name)

    def get_entity_by_id(self, entity_id: str):
        return self.plugin.get_entity_by_id(self.name, entity_id)


class InputDataError(Exception):
    """Raised when the data does not match the given schema, or is otherwise malformatted"""
