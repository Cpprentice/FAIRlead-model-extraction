import importlib
import json
import pkgutil
import sys
from argparse import ArgumentParser, ArgumentError, Namespace
from pathlib import Path
from typing import List, Callable

from simpler_core.dot import create_graph, filter_graph
from simpler_core.plugin import DataSourcePlugin, DataSourceCursor, DataSourceType
from simpler_core.schema import serialize_entity_list_to_yaml, load_external_schema_from_yaml, extend_schema_from_yaml, \
    apply_schema_correction_if_available, introduce_inverse_relations
from simpler_core.storage import ManualFilesystemDataSourceStorage


def get_arg_parser(plugins: List[DataSourceType]) -> ArgumentParser:
    plugin_names = [p.name for p in plugins]
    parser = ArgumentParser(prog='simpler-cli')
    sub_commands = parser.add_subparsers(dest='command')
    extract_command_parser = ecp = sub_commands.add_parser('extract')
    ecp.add_argument('-p', '--plugin', required=True, help='The plugin to use to extract schema data',
                     choices=plugin_names)
    ecp.add_argument('-i', '--input', action='append', required=True,
                     help='Specify the input file paths and the input name of the plugin like "input_name:path"')
    ecp.add_argument('-f', '--format', choices=['RDF', 'DOT', 'JSON', 'YAML'], default='JSON')
    ecp.add_argument('-o', '--output', help='Write to target file instead of STDOUT')
    ecp.add_argument('--select-entity', action='append',
                     help='Specify a list of entities the diagram shall show up plus up to "distance" neighbors')
    ecp.add_argument('--distance', metavar='<int>', type=int, default=2,
                     help='Rendering distance for DOT only used with --select-entity')
    ecp.add_argument('--dont-generate-inverse-relations', type=bool, default=False,
                     help='Disable the automatic generation of inverse relations')
    ecp.add_argument('--hide-arguments', type=bool, default=False,
                     help='Flag to prevent argument rendering')

    schema_merge_command_parser = smcp = sub_commands.add_parser('schema')
    smcp.add_argument('base_schema_file', metavar='<base-schema-file>', help='A full spec file')
    smcp.add_argument('extension_schema_files', nargs='+', help='A list of extension files to add')

    dot_command_parser = dcp = sub_commands.add_parser('dot')
    dcp.add_argument('schema_file', metavar='<schema-file>', help='the schema file to generate dot for')
    dcp.add_argument('--select-entity', action='append',
                     help='Specify a list of entities the diagram shall show up plus up to "distance" neighbors')
    dcp.add_argument('--distance', metavar='<int>', type=int, default=2,
                     help='Rendering distance for DOT only used with --select-entity')
    return parser


def command_registry(
        command_name: str,
        command_func: Callable[[Namespace, ArgumentParser], None] | None = None
) -> Callable[[Namespace, ArgumentParser], None] | None:
    if not hasattr(command_registry, 'store'):
        command_registry.store = {}
    if command_func is None:
        return command_registry.store[command_name]
    command_registry.store[command_name] = command_func


def command(
        command_name: str
) -> Callable[[Callable[[Namespace, ArgumentParser], None]], Callable[[Namespace, ArgumentParser], None]]:
    def wrapper(command_func: Callable[[Namespace, ArgumentParser], None]):
        command_registry(command_name, command_func)
        return command_func
    return wrapper


def execute_command(args: Namespace, parser: ArgumentParser):
    command_func = command_registry(args.command)
    command_func(args, parser)


@command('schema')
def schema_command(args: Namespace, parser: ArgumentParser):
    with open(args.base_schema_file, 'rb') as base_stream:
        list_of_base_entities = load_external_schema_from_yaml(base_stream)
    for extension_file in args.extension_schema_files:
        with open(extension_file, 'rb') as extension_stream:
            list_of_base_entities = extend_schema_from_yaml(list_of_base_entities, extension_stream)
    print(serialize_entity_list_to_yaml(list_of_base_entities))


@command('extract')
def extract_command(args: Namespace, parser: ArgumentParser):
    plugins = DataSourcePlugin.get_data_source_types()

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

    entities = apply_schema_correction_if_available(entities, storage, 'cli')

    if not args.dont_generate_inverse_relations:
        introduce_inverse_relations(entities)

    output_string = ''

    if args.format == 'DOT':
        dot = create_graph(entities, show_attributes=not args.hide_arguments)
        if args.select_entity:
            dot = filter_graph(dot, args.select_entity, args.distance)
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


@command('dot')
def dot_command(args: Namespace, parser: ArgumentParser):
    with open(args.schema_file, 'rb') as base_stream:
        list_of_base_entities = load_external_schema_from_yaml(base_stream)
    graph = create_graph(list_of_base_entities)
    if args.select_entity:
        graph = filter_graph(graph, args.select_entity, args.distance)
    print(str(graph))


def load_all_plugin_modules():
    """
    This function imports all simpler plugin modules such that the plugin base class can recognize all its subclasses
    """
    for module in pkgutil.iter_modules():
        if module.name.startswith('simpler_plugin_'):
            importlib.import_module(module.name)


def main():

    load_all_plugin_modules()
    plugins = DataSourcePlugin.get_data_source_types()
    parser = get_arg_parser(plugins)
    args = parser.parse_args(sys.argv[1:])
    execute_command(args, parser)


if __name__ == '__main__':
    main()
