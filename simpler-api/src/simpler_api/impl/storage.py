import io
from pathlib import Path

from simpler_core.storage import FilesystemDataSourceStorage


def get_storage():
    # TODO discuss whether this could come from an env variable - For now we use a relative path
    base_path = Path('storage')
    return FilesystemDataSourceStorage(base_path)


# TODO remove this temporary data adding
# storage = get_storage()
# buffer = io.StringIO('postgres://postgres:postgres@localhost/postgres')
# buffer.seek(0, io.SEEK_SET)
# storage.insert_data('mondial', 'SQL', {
#     'connector': buffer
# })
