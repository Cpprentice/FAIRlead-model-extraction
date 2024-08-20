import sys
from typing import Tuple

from simpler_model import Cardinality


def create_cardinality(cardinality_tuple: Tuple[int, int]) -> Cardinality:
    if cardinality_tuple == (0, sys.maxsize):
        return Cardinality(cardinality='any')
    if cardinality_tuple == (1, sys.maxsize):
        return Cardinality(cardinality='oneOrMore')
    if cardinality_tuple == (0, 1):
        return Cardinality(cardinality='oneOrNone')
    if cardinality_tuple == (1, 1):
        return Cardinality(cardinality='exactlyOne')
    return Cardinality(cardinality='unsupported')


def merge_cardinalities(c_a: Tuple[int, int], c_b: Tuple[int, int]) -> Tuple[int, int]:
    min_a, max_a = c_a
    min_b, max_b = c_b
    if min_a != min_b and min_a != 0 and min_b != 0:
        raise ValueError('The cardinalities to merge have both non-zero min values that are not equal')
    if max_a != max_b and max_a != sys.maxsize and max_b != sys.maxsize:
        raise ValueError('The cardinalities to merge have both non-limited max values that are not equal')
    return max(min_a, min_b), min(max_a, max_b)
