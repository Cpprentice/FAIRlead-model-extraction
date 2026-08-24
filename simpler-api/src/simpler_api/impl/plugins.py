import functools
import importlib
import inspect
import pkgutil
from typing import Any, Callable

from fastapi import Request, HTTPException

from fairlead_core.caching import Pipeline
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


def inject_cursor(endpoint_method: Callable[[type, Request, ...], Any]):
    signature = inspect.signature(endpoint_method)
    @functools.wraps(endpoint_method)
    def wrapper(self, request: Request, *args: Any, **kwargs: Any) -> Any:

        bound = signature.bind(self, request, *args, **kwargs, cursor=None, pipeline=None)
        schema_id = bound.arguments.get('schemaId')
        try:
            # we should be able to directly get a cursor here based on the schema Id - if not we issue a 404
            cursor = get_cursor(request, schema_id)
        except:
            raise HTTPException(status_code=404, detail="Schema not found")
        kwargs['cursor'] = cursor
        return endpoint_method(self, request, *args, **kwargs)
    return wrapper


def use_caching_pipeline(endpoint_method: Callable[[type, Request, ...], Any]):
    # signature = inspect.signature(endpoint_method)
    @functools.wraps(endpoint_method)
    def wrapper(self, request: Request, *args: Any, cursor: DataSourceCursor, **kwargs: Any) -> Any:   # I believe as this is the final result the call fails - needs debugging
        hash_reset_depth = int(request.query_params.get('_hash_reset', 0))
        with cursor.get_cache(hash_reset_depth) as cache:
            pipeline = Pipeline(cache, first_stage_input=cursor)  # result_type=signature.return_annotation)
            kwargs['cursor'] = cursor
            kwargs['pipeline'] = pipeline
            endpoint_method(self, request, *args, **kwargs)  # no longer expected to return something
            return pipeline.run()
    return wrapper
