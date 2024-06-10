from typing import List

from simpler_core.plugin import DataSourcePlugin, DataSourceType
from simpler_model import EntityLink, Entity


class TabularDataSourceType(DataSourceType):
    name = 'Tabular'
    inputs = ['data']


class SqlDataSourcePlugin(DataSourcePlugin):

    data_source_type = TabularDataSourceType()

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        pass

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass
