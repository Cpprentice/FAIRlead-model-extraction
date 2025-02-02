# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401
from fastapi import Request

from simpler_api.models.data_source import DataSource


file = bytes


class BaseDataSourceApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDataSourceApi.subclasses = BaseDataSourceApi.subclasses + (cls,)
    def add_data_source_meta(
        self,
        request: Request,
        data_source: DataSource,
    ) -> DataSource:
        """desc"""
        ...


    def get_all_data_source_meta(
        self,
        request: Request,
    ) -> List[DataSource]:
        """desc"""
        ...


    def get_data_source_content(
        self,
        request: Request,
        dataSourceId: str,
        pluginInputField: str,
    ) -> file:
        """desc"""
        ...


    def get_data_source_meta(
        self,
        request: Request,
        dataSourceId: str,
    ) -> List[DataSource]:
        """desc"""
        ...


    def upload_data_source_content(
        self,
        request: Request,
        dataSourceId: str,
        pluginInputField: str,
    ) -> None:
        """desc"""
        ...
