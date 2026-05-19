import copy
import functools
import inspect
import marshal
import pathlib
import pickle
import shelve
from typing import Callable, Any, Self

import xxhash



class DiskCache:

    _cache_file_name = '__cache'
    _private_token = object()

    def __init__(self, base_path: pathlib.Path, reset_depth: int, token=None):
        if token is not self._private_token:
            raise RuntimeError("Don't instantiate DiskCache without the create_cache factory")
        self.shelf_path = base_path / self._cache_file_name
        # elf.base_path = base_path
        self.reset_depth = reset_depth
        # self.depth = 0
        self.current_depth = 0
        self.shelf = None

    @property
    def depth(self) -> int:
        keys = list(self.shelf.keys())
        return max(map(lambda key: int(key[16:]) + 1, keys)) if len(keys) > 0 else 0

    def __enter__(self):
        # self.shelf = shelve.open(str(self.base_path / self._cache_file_name))
        self.shelf = shelve.open(self.shelf_path)
        # keys = list(self.shelf.keys())
        # self.depth = max(map(lambda key: int(key[16:]) + 1, keys)) if len(keys) > 0 else 0
        self.current_depth = self.depth -1  # this is now from -1 to n-1 # max(self.depth - 1, 0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.shelf is not None:
            self.shelf.close()
            self.shelf = None

    def get_next(self, args: list) -> Any | None:
        key = self._make_key(args)
        key += str(self.current_depth)
        value = self.shelf.get(key, None)
        if self.reset_depth > 0:
            self.reset_depth -= 1
            del self.shelf[key]  # make sure the cache item is gone for following runs
            value = None
        # self.current_depth = max(self.current_depth - 1, 0)
        if value is None:
            self.current_depth -= 1
        return value

    def store(self, data: Any, args: list):
        key = self._make_key(args)
        key += str(self.current_depth + 1)
        self.shelf[key] = data
        self.current_depth += 1

    @classmethod
    def create_cache(cls, base_path: pathlib.Path, reset_depth: int = 0, init_depth: int = 1) -> Self:
        cache = DiskCache(base_path, reset_depth, cls._private_token)
        frame = inspect.currentframe()
        for i in range(0, init_depth):
            frame = frame.f_back

        frame.f_locals['__cache'] = cache
        return cache

    @classmethod
    def get_active_cache(cls, search_depth=10) -> Self | None:
        calling_frame = inspect.currentframe().f_back
        frame = calling_frame
        while search_depth > 0 and frame is not None:
            cache = frame.f_locals.get('__cache', None)
            if cache is not None:
                calling_frame.f_locals['__cache'] = cache
                return cache
            frame = frame.f_back
            search_depth -= 1
        return None

    @staticmethod
    def _make_key(args: list):
        key = copy.copy(args)
        key += tuple(type(v) for v in args)
        byte_key = pickle.dumps(key)  # marshal does not work with types - pickle does
        hashed_key = xxhash.xxh3_64(byte_key)
        return hashed_key.hexdigest()


class PipelineStage:
    def __init__(self, cache: DiskCache, args: list, func: Callable):
        self.cache = cache
        # self.result = None
        self.args = args
        self.func = func

    def __call__(self, *args):
        return self.func(*args)
        # if self.result is not None:
        #     self.cache.store(self.result, self.args)


class Pipeline:
    def __init__(self, cache: DiskCache):
        self.cache = cache
        self.ops = []

    def operation(self, arg_list: list) -> Callable:
        def decorator(func):
            # def wrapper(*args, **kwargs):
            #     return func(*args, **kwargs)
            previous_args = self.ops[-1].args if len(self.ops) > 0 else []
            self.ops.append(PipelineStage(self.cache, previous_args + arg_list, func))
            return func
        return decorator

    def run(self):
        cache_idx = min(len(self.ops) - 1, self.cache.current_depth)
        # cache_idx = self.cache.current_depth
        result = None
        # for cache_idx in range(len(self.ops) - 1, -1, -1):
        while cache_idx >= 0:
            stage = self.ops[cache_idx]
            result = self.cache.get_next(stage.args)
            if result is not None:
                break
            cache_idx -= 1

        # result = None
        args = tuple([]) if result is None else (result if isinstance(result, tuple) else tuple([result]))
        for idx in range(cache_idx + 1, len(self.ops)):
            stage = self.ops[idx]
            result = stage(*args)
            self.cache.store(result, stage.args)
            args = result if isinstance(result, tuple) else tuple([result])
        return result
