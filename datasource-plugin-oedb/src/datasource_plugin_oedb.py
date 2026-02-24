import io
import json
from typing import List
import urllib.request
import urllib.response

from simpler_core.plugin import DataSourceType, InputFlag, DataSourcePlugin, EntityLink
from simpler_model import Entity, Attribute


class OEDBDataSourceType(DataSourceType):
    name = 'OpenEnergyDatabase'
    inputs = [
        ('config', InputFlag.TEXT | InputFlag.SHOW_IN_JSON)
    ]
    input_validation_statement = r'config'


class OEDBDataSourcePlugin(DataSourcePlugin):
    data_source_type = OEDBDataSourceType()

    @staticmethod
    def _read_config(stream: io.TextIOBase) -> tuple[str, str]:
        config = json.load(stream)
        return config['schema'], config['table']

    def _make_request(self, schema_name: str, path: str, is_json=True) -> dict | list | str | tuple[bytes, str]:
        with self.storage.get_data(schema_name) as stream_lookup:
            oedb_schema, oedb_table = self._read_config(io.TextIOWrapper(stream_lookup['config'], encoding='utf-8'))

        with urllib.request.urlopen(
                f'https://openenergyplatform.org/api/v0/schema/{oedb_schema}/tables/{oedb_table}/{path}'
        ) as response:
            if is_json:
                return json.load(response)
            return response.read(), response.getheader('Content-Type')

    def _fetch_meta_json(self, schema_name: str) -> dict | list | str:
        return self._make_request(schema_name, 'meta')

    def _fetch_raw_data(self, schema_name: str, entity_id: str) -> tuple[bytes, str]:
        return self._make_request(schema_name, 'rows', is_json=False)

    def get_strong_entities(self, name: str) -> List[Entity]:
        pass

    def get_all_entities(self, name: str) -> List[Entity]:
        meta = self._fetch_meta_json(name)
        title = meta['resources'][0]['title']
        fields = meta['resources'][0]['schema']['fields']

        entity = Entity(
            entity_name=[title],
            has_attribute=[
                Attribute(
                    attribute_name=[field['name']],
                    has_attribute_modifier=[]
                )
                for field in fields
            ],
            is_subject_in_relation=[],
            is_object_in_relation=[],
            has_entity_modifier=[],
        )
        return [entity]

    def get_related_entity_links(self, name: str) -> List[EntityLink]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass

    def get_raw_data_by_entity(self, name: str, entity_id: str) -> tuple[bytes, str]:
        return self._fetch_raw_data(name, entity_id)
