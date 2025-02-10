import io
from pathlib import Path

from simpler_core.storage import FilesystemDataSourceStorage


def get_storage():
    # TODO discuss whether this could come from an env variable - For now we use a relative path
    base_path = Path('storage')
    return FilesystemDataSourceStorage(base_path)
