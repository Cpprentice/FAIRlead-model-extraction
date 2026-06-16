import json
from functools import cache
from typing import List
import urllib.parse
import urllib.request

from fairlead_core.cardinality import create_cardinality
from fairlead_core.plugin import DataSourceType, DataSourcePlugin, EntityLink, InputFlag
from simpler_model import Entity, Attribute, Relation, EntityModifier


class InfluxDataSourceType(DataSourceType):
    name = 'Influx'
    inputs = [
        ('url', InputFlag.TEXT | InputFlag.SHOW_IN_JSON),
        ('user', InputFlag.TEXT | InputFlag.SECURE),
        ('password', InputFlag.TEXT | InputFlag.SECURE),
        ('token', InputFlag.TEXT | InputFlag.SECURE)
    ]
    input_validation_statement = r'(password,url,user|token,url)'


class InfluxDataSourcePlugin(DataSourcePlugin):

    @cache
    def _get_auth_params(self, schema_name: str) -> tuple[str, dict]:
        query_params = {}
        with self.storage.get_data(schema_name) as stream_lookup:
            url = stream_lookup['url'].read().decode('utf-8')
            if 'token' in stream_lookup:
                token = stream_lookup['token'].read().decode('utf-8')
                # TODO add token to query params
            else:
                user = stream_lookup['user'].read().decode('utf-8')
                password = stream_lookup['password'].read().decode('utf-8')
                if user != '':
                    query_params['u'] = user
                    query_params['p'] = password
        return url, query_params

    @staticmethod
    def parse_response(response: dict) -> list[dict[str, list[dict[str, str]]]]:
        assert 'results' in response
        results = response['results']
        output_data = {}
        for result in results:  # Results has more than one element if you concatenate queries with semicolon
            query_number = result['statement_id']
            single_result = {}
            output_data[query_number] = single_result

            if 'error' in result:
                single_result['error'] = result['error']
            elif 'series' in result:
                for measurement_data in result['series']:
                    measurement_name = measurement_data['name']
                    single_result[measurement_name] = [
                        {
                            key: value
                            for key, value in zip(measurement_data['columns'], values)
                        }
                        for values in measurement_data['values']
                    ]
        statement_count = max(output_data.keys()) + 1
        return [output_data[i] for i in range(statement_count)]

    def _make_request(self, schema_name: str, query: str, database_name: str | None = None):
        url, query_params = self._get_auth_params(schema_name)
        query_params['q'] = query
        if database_name is not None:
            query_params['db'] = database_name

        query_string = urllib.parse.urlencode(query_params)

        # Construct the full URL with the query string
        full_url = f"{url}?{query_string}"

        # Make the GET request
        with urllib.request.urlopen(full_url) as response:
            data = json.load(response)

        return data

    def get_all_entities(self, name: str) -> List[Entity]:
        databases_response = self._make_request(name, 'SHOW DATABASES')
        databases = [x[0] for x in databases_response['results'][0]['series'][0]['values'] if not x[0].startswith('_')]

        entities = []
        for database_name in databases:

            combo_response = self._make_request(name, 'SHOW MEASUREMENTS ; SHOW FIELD KEYS; SHOW TAG KEYS ', database_name)
            parsed_combo_data = self.parse_response(combo_response)
            measurements, field_keys, tag_keys = parsed_combo_data

            entities.append(Entity(
                entity_name=[database_name],
                has_attribute=[],
                is_subject_in_relation=[],
                is_object_in_relation=[],
                has_entity_modifier=[],
            ))

            for measurement in measurements['measurements']:
                measurement_name = measurement['name']
                attributes = []
                if measurement_name in field_keys:
                    for field_key in field_keys[measurement_name]:
                        attributes.append(Attribute(
                            attribute_name=[field_key['fieldKey']],
                            has_attribute_modifier=[]
                        ))
                if measurement_name in tag_keys:
                    for tag_key in tag_keys[measurement_name]:
                        attributes.append(Attribute(
                            attribute_name=[tag_key['tagKey']],
                            has_attribute_modifier=[]
                        ))

                entities.append(Entity(
                    entity_name=[measurement_name],
                    has_attribute=attributes,
                    is_subject_in_relation=[
                        Relation(
                            has_object_entity=database_name,
                            has_subject_entity=measurement_name,
                            object_cardinality=create_cardinality((1, 1)),
                            subject_cardinality=create_cardinality((1, 1)),
                            has_relation_modifier=[],
                            relation_name=['belongsToDatabase'],
                            has_attribute=[]
                        )
                    ],
                    is_object_in_relation=[],
                    has_entity_modifier=[],
                ))
        return entities

        # measurements_response = self._make_request(name, 'SHOW MEASUREMENTS', database_name)
        # measurement_names = [x[0] for x in measurements_response['results'][0]['series'][0]['values']]
        #
        # all_field_keys_response = self._make_request(name, 'SHOW FIELD KEYS', database_name)
        # all_tag_keys_response = self._make_request(name, 'SHOW TAG KEYS', database_name)
        # _ = 42
        #
        # for measurement_name in measurement_names:
        #     field_keys_response = self._make_request(
        #         name, f'SHOW FIELD KEYS FROM "{measurement_name}"', database_name
        #     )
        #
        #     field_keys = [x[0] for x in field_keys_response['results'][0]['series'][0]['values']]
        # _ = 42

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        pass

    data_source_type = InfluxDataSourceType()

