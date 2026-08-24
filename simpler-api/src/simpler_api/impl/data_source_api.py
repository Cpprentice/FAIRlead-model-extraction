import asyncio
import io
from typing import List

import yaml
from fastapi import HTTPException, Request

from simpler_api.apis.data_source_api_base import BaseDataSourceApi
from simpler_api.impl.plugins import get_cursor
from simpler_api.impl.response import wrap_response_according_to_request
from simpler_api.impl.storage import get_storage
from fairlead_core.plugin import DataSourcePlugin, InputFlag
from simpler_model import DataSource, DataSourceTextDataInner


import asyncio
import threading
from typing import Any, Awaitable, Iterable, Optional, TypeVar

T = TypeVar("T")


class sync_await:
    def __enter__(self) -> "sync_await":
        self._loop = asyncio.new_event_loop()
        self._looper = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._looper.start()
        return self

    def __call__(self, coro: Awaitable[T], timeout: Optional[float] = None) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def __exit__(self, *exc_info: Any) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._looper.join()
        self._loop.close()


class DataSourceApi(BaseDataSourceApi):

    @staticmethod
    def _get_data_source_by_name(name: str) -> DataSource:
        storage = get_storage()
        plugin_name = storage.get_plugin_name(name)
        class_ = DataSourcePlugin.get_plugin_class(plugin_name)
        input_definitions = class_.data_source_type.inputs

        with storage.get_data(name) as stream_lookup:
            keys = set(stream_lookup.keys())
            all_input_names = set(x[0] for x in input_definitions)
            populated_input_fields = sorted(keys & all_input_names)

            in_json_input_names = set(
                x[0]
                for x in input_definitions
                if x[1] & (InputFlag.SHOW_IN_JSON | InputFlag.SECURE) == InputFlag.SHOW_IN_JSON
            ) & keys

            text_data = [
                DataSourceTextDataInner(
                    input_field=name,
                    value=stream_lookup[name].read().decode('utf-8')
                )
                for name in in_json_input_names
            ]

        return DataSource(
            plugin=plugin_name,
            id=name,
            # description='',
            populated_input_fields=populated_input_fields,
            text_data=text_data
        )

    @staticmethod
    def _get_input_field_flag(data_source_name: str, field_name: str) -> int:
        storage = get_storage()
        plugin_name = storage.get_plugin_name(data_source_name)
        class_ = DataSourcePlugin.get_plugin_class(plugin_name)
        input_definitions = class_.data_source_type.inputs
        field_flags = [x[1] for x in input_definitions if x[0] == field_name]
        return field_flags[0]

    def add_data_source_meta(
        self,
        request: Request,
        data_source: DataSource,
    ) -> DataSource:
        storage = get_storage()
        storage.insert_data(
            data_source.id,
            data_source.plugin,
            {
                item.input_field: io.BytesIO(item.value.encode('utf-8'))
                for item in data_source.text_data
            } if data_source.text_data else {}
        )
        return wrap_response_according_to_request(request, self._get_data_source_by_name(data_source.id))

    def get_all_data_source_meta(
        self,
        request: Request,
    ) -> List[DataSource]:
        storage = get_storage()
        data_source_names = storage.list_available_data()

        data_sources = []
        for name in data_source_names:
            data_sources.append(self._get_data_source_by_name(name))
        return wrap_response_according_to_request(request, data_sources)

    def get_data_source_content(
        self,
        request: Request,
        dataSourceId: str,
        pluginInputField: str,
    ) -> bytes:
        valid = True
        try:
            flag = self._get_input_field_flag(dataSourceId, pluginInputField)
            if flag & InputFlag.SECURE:
                valid = False
            else:
                storage = get_storage()
                with storage.get_data(dataSourceId) as stream_lookup:
                    return stream_lookup[pluginInputField].read()
        except KeyError:
            valid = False
        raise HTTPException(status_code=404, detail="Data source or field not found")

    def get_data_source_meta(
        self,
        request: Request,
        dataSourceId: str,
    ) -> List[DataSource]:
        return wrap_response_according_to_request(request, self._get_data_source_by_name(dataSourceId))

    async def upload_data_source_content(
        self,
        request: Request,
        dataSourceId: str,
        pluginInputField: str,
    ) -> None:
        body = await request.body()
        # with sync_await() as await_:
        #     body = await_(request.body())
        # body = asyncio.get_event_loop().run_until_complete(request.body())
        # body = request.body()
        storage = get_storage()
        plugin_name = storage.get_plugin_name(dataSourceId)
        storage.insert_data(dataSourceId, plugin_name, {pluginInputField: io.BytesIO(body)})
