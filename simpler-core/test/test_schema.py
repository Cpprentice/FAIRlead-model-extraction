from unittest.mock import Mock

import pytest

from simpler_core.schema import get_precedence_keys, merge_schema_dicts, merge_schema_lists


def test_get_precedence_keys_with_secondary_precedence():
    result = get_precedence_keys([
        [
            ['table1'],
            ['table2']
        ],
        [
            ['Fruit', 'table1'],
            ['Vegetable', 'table2']
        ]
    ])
    assert result == [('Fruit', 'table1'), ('Vegetable', 'table2')]


def test_get_precedence_keys_with_partial_precedence():
    result = get_precedence_keys([
        [
            ['table1'],
            ['table2']
        ],
        [
            ['Fruit', 'table1'],
            ['Vegetable']
        ]
    ])
    assert result == [('Fruit', 'table1'), ('table2',), ('Vegetable',)]


def test_get_precedence_keys_with_more_than_two_lists():
    result = get_precedence_keys([
        [
            ['table1'],
            ['table2']
        ],
        [
            ['Fruit', 'table1'],
            ['Vegetable']
        ],
        [
            ['Vegetable', 'table2']
        ]
    ])
    assert result == [('Fruit', 'table1'), ('Vegetable', 'table2')]


def test_merge_schema_dicts_simple():
    result = merge_schema_dicts({
        'key1': 123,
        'key2': 456
    }, {
        'key2': 1024
    })
    assert result == {'key1': 123, 'key2': 1024}


def test_merge_schema_dicts_simple_new_key():
    result = merge_schema_dicts({
        'key1': 123
    }, {
        'key2': 1024
    })
    assert result == {'key1': 123, 'key2': 1024}


def test_merge_schema_dicts_simple_list(mocker):
    mocker.patch('simpler_core.schema.merge_schema_lists', Mock(side_effect=lambda a, b: b))
    result = merge_schema_dicts({
        'key1': 123,
        'key2': [123]
    }, {
        'key2': [456]
    })
    assert result == {'key1': 123, 'key2': [456]}


def test_merge_schema_dicts_simple_nested():
    result = merge_schema_dicts({
        'key1': 123,
        'key2': {'inner': 123}
    }, {
        'key2': {'inner': 567}
    })
    assert result == {'key1': 123, 'key2': {'inner': 567}}


def test_merge_schema_dicts_simple_base_is_none():
    result = merge_schema_dicts({
        'key1': None
    }, {
        'key1': '123'
    })
    assert result == {'key1': '123'}


def test_merge_schema_lists_empty_base():
    result = merge_schema_lists([], [123])
    assert result == [123]


def test_merge_schema_lists_non_named_list(mocker):
    mocker.patch('simpler_core.schema.get_name_key', Mock(return_value=None))
    result = merge_schema_lists([123], [456])
    assert result == [456]


def test_merge_schema_lists_named_list_independent(mocker):
    mocker.patch('simpler_core.schema.get_name_key', Mock(return_value='name'))
    mocker.patch('simpler_core.schema.get_precedence_keys_from_dicts', Mock(return_value=[('abc',), ('def',)]))
    result = merge_schema_lists([
        {
            'name': ['abc']
        }
    ], [
        {
            'name': ['def']
        }
    ])
    assert result == [{'name': ['abc']}, {'name': ['def']}]


def test_merge_schema_lists_named_list_merging(mocker):
    mocker.patch('simpler_core.schema.get_name_key', Mock(return_value='name'))
    mocker.patch('simpler_core.schema.get_precedence_keys_from_dicts', Mock(return_value=[('abc', 'def')]))
    mocker.patch('simpler_core.schema.merge_schema_dicts', Mock(return_value={'name': ['def', 'abc']}))
    result = merge_schema_lists([
        {
            'name': ['abc']
        }
    ], [
        {
            'name': ['def', 'abc']
        }
    ])
    assert result == [{'name': ['def', 'abc']}]
