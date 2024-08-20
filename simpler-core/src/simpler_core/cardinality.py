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
