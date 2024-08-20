import importlib
import pkgutil

from fastapi import Request

from simpler_api.impl.storage import get_storage
from simpler_core.plugin import DataSourceCursor, DataSourcePlugin


for module in pkgutil.iter_modules():
    if module.name.startswith('simpler_plugin_'):
        importlib.import_module(module.name)


# TODO remove legacy request passing to plugins -> URLs are now created only in the API code itself
def get_cursor(request: Request, name: str) -> DataSourceCursor:
    storage = get_storage()
    plugin_name = storage.get_plugin_name(name)
    class_ = DataSourcePlugin.get_plugin_class(plugin_name)
    plugin = class_(storage, lambda *args, **kwargs: str(request.url_for(*args, **kwargs)))
    return plugin.get_cursor(name)
