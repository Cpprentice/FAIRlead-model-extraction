import io
from functools import cache
from pathlib import Path

from fairlead_core.identifiers import YamlFileIdentifierStorage, IdentifierStorageService
from fairlead_core.storage import FilesystemDataSourceStorage


def get_storage():
    # TODO discuss whether this could come from an env variable - For now we use a relative path
    base_path = Path('storage')
    return FilesystemDataSourceStorage(base_path)


# @cache
def get_id_storage() -> IdentifierStorageService:
    # storage = get_storage()
    # return YamlFileIdentifierStorage(Path('identifiers.yaml'), storage)
    return YamlFileIdentifierStorage(Path('identifiers.yaml'))
