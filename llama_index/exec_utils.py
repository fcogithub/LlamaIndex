import copy

from typing import Any, Mapping
from types import CodeType
from _typeshed import ReadableBuffer

ALLOWED_IMPORTS = {'math', 'time'}

def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in ALLOWED_IMPORTS:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Import of module '{name}' is not allowed")

ALLOWED_BUILTINS = {
    'abs': abs,
    'all': all,
    'any': any,
    'ascii': ascii,
    'bin': bin,
    'bool': bool,
    'bytearray': bytearray,
    'bytes': bytes,
    'chr': chr,
    'complex': complex,
    'divmod': divmod,
    'enumerate': enumerate,
    'filter': filter,
    'float': float,
    'format': format,
    'frozenset': frozenset,
    'getattr': getattr,
    'hasattr': hasattr,
    'hash': hash,
    'hex': hex,
    'int': int,
    'isinstance': isinstance,
    'issubclass': issubclass,
    'iter': iter,
    'len': len,
    'list': list,
    'map': map,
    'max': max,
    'min': min,
    'next': next,
    'oct': oct,
    'ord': ord,
    'pow': pow,
    'print': print,
    'range': range,
    'repr': repr,
    'reversed': reversed,
    'round': round,
    'set': set,
    'setattr': setattr,
    'slice': slice,
    'sorted': sorted,
    'str': str,
    'sum': sum,
    'tuple': tuple,
    'type': type,
    'zip': zip,
    # Constants
    'True': True,
    'False': False,
    'None': None,
    '__import__': _restricted_import
}


def safe_eval(
    __source: str | ReadableBuffer | CodeType,
    __globals: dict[str, Any] | None = None,
    __locals: Mapping[str, object] | None = None,
) -> Any:
    pass


def safe_exec(
    __source: str | ReadableBuffer | CodeType,
    __globals: dict[str, Any] | None = None,
    __locals: Mapping[str, object] | None = None,
) -> None:
    pass
