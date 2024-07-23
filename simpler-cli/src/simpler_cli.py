import importlib
import json
import pkgutil
import sys
from argparse import ArgumentParser, ArgumentError
from pathlib import Path
from typing import List

from simpler_core.dot import create_graph
from simpler_core.plugin import DataSourcePlugin, DataSourceCursor, DataSourceType
from simpler_core.schema import serialize_entity_list_to_yaml
from simpler_core.storage import ManualFilesystemDataSourceStorage


def get_arg_parser(plugins: List[DataSourceType]) -> ArgumentParser:
    plugin_names = [p.name for p in plugins]
    parser = ArgumentParser(prog='simpler-cli')
    parser.add_argument('-p', '--plugin', required=True, help='The plugin to use to extract schema data',
                        choices=plugin_names)
    parser.add_argument('-i', '--input', action='append', required=True,
                        help='Specify the input file paths and the input name of the plugin like "input_name:path"')
    parser.add_argument('-f', '--format', choices=['RDF', 'DOT', 'JSON', 'YAML'], default='JSON')
    parser.add_argument('-o', '--output', help='Write to target file instead of STDOUT')
    return parser


def main():

    for module in pkgutil.iter_modules():
        if module.name.startswith('simpler_plugin_'):
            importlib.import_module(module.name)

    plugins = DataSourcePlugin.get_data_source_types()
    parser = get_arg_parser(plugins)
    args = parser.parse_args(sys.argv[1:])

    selected_plugin, = [p for p in plugins if p.name == args.plugin]
    input_lookup = {
        input_name: Path(input_path)
        for input_string in args.input
        for input_name, input_path in [input_string.split(':')]
    }

    if not selected_plugin.validate_inputs(input_lookup.keys()):
        # TODO get input argument as first argument
        raise ArgumentError(parser._option_string_actions['-i'], 'Provided set of inputs is invalid')

    class_ = DataSourcePlugin.get_plugin_class(args.plugin)
    storage = ManualFilesystemDataSourceStorage(files={
        'cli': (args.plugin, {
            input_name: Path(input_path)
            for input_string in args.input
            for input_name, input_path in [input_string.split(':')]
        })
    })
    plugin = class_(storage, lambda *args, **kwargs: 'file:///blub')
    cursor: DataSourceCursor = plugin.get_cursor('cli')

    entities = cursor.get_all_entities()
    output_string = ''

    if args.format == 'DOT':
        dot = create_graph(entities, show_attributes=True)
        output_string = str(dot)
    elif args.format == 'JSON':
        dicts = [m.dict() for m in entities]
        output_string = json.dumps(dicts, indent=4)
    elif args.format == 'YAML':
        output_string = serialize_entity_list_to_yaml(entities)

    if args.output is not None:
        with open(args.output, 'w') as stream:
            stream.write(output_string)
    else:
        print(output_string)


if __name__ == '__main__':
    main()
