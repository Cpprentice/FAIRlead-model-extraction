import importlib
import pkgutil

from fastapi import Request

from simpler_api.impl.storage import get_storage
from fairlead_core.plugin import DataSourceCursor, DataSourcePlugin
from fairlead_core.settings import OptimizationSettings

for module in pkgutil.iter_modules():
    if module.name.startswith('simpler_plugin_'):
        importlib.import_module(module.name)
    if module.name.startswith('datasource_plugin_'):
        importlib.import_module(module.name)


def get_cursor(request: Request, name: str) -> DataSourceCursor:
    storage = get_storage()
    plugin_name = storage.get_plugin_name(name)
    class_ = DataSourcePlugin.get_plugin_class(plugin_name)
    plugin = class_(storage)
    return plugin.get_cursor(name, OptimizationSettings(**request.query_params))
