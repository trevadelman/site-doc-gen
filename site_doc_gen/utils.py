"""
Utility functions for site-doc-gen
"""

from fnmatch import fnmatch
from typing import Union, List, TypeVar, Any

T = TypeVar('T')

def format_number(num: int) -> str:
    """Format large numbers with K/M suffixes"""
    if num > 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num > 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

def match_path(path: str, patterns: Union[str, List[str]]) -> bool:
    """Match a path against one or more glob patterns"""
    if isinstance(patterns, str):
        patterns = [patterns]
    return any(fnmatch(path, pattern) for pattern in patterns)

def ensure_array(input_value: Union[T, List[T]]) -> List[T]:
    """Convert a single value or list to a list"""
    if isinstance(input_value, list):
        return input_value
    return [input_value]
