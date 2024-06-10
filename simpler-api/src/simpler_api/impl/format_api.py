from typing import List

from fastapi import HTTPException, Request, Response

from simpler_api.impl.plugins import get_cursor
from simpler_api.apis.format_api_base import BaseFormatApi
from simpler_api.models.format import Format
from simpler_core.plugin import DataSourceCursor, DataSourcePlugin

class FormatApi(BaseFormatApi):
    def get_all_formats(
        self,
        request: Request,
    ) -> List[Format]:
        return [
            Format(name=data_type.name, inputs=data_type.inputs)
            for data_type in DataSourcePlugin.get_data_source_types()
        ]
