"""Annotation functions for the SBEM module."""

import re
from typing import Any

import numpy as np


def nan_to_none_or_str(v: Any) -> str | None | Any:
    """Converts NaN to None and leaves strings as is.

    Args:
        v (Any): Value to convert

    Returns:
        v (None | str | Any): Converted value
    """
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return v


def str_to_bool(v: str | bool) -> bool:
    """Converts a string to a boolean if necessary.

    Args:
        v (str | bool): Value to convert

    Returns:
        bool: Converted value
    """
    if isinstance(v, bool):
        return v
    return v.lower() == "true"


def str_to_float_list(v: str | list) -> list[float]:
    """Converts a string to a list of floats.

    Args:
        v (str | list): String to convert

    Returns:
        list[float]: List of floats
    """
    if isinstance(v, list):
        return [float(x) for x in v]
    if v == "[]":
        return []
    if not re.match(r"^\[.*\]$", v):
        raise ValueError(f"STRING:NOT_LIST:{v}")
    v = v[1:-1]
    if not re.match(r"^[\-0-9\., ]*$", v):
        raise ValueError(f"STRING:NOT_LIST:{v}")
    return [float(x) for x in v.replace(" ", "").split(",")]
