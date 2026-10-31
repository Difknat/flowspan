"""``@flowspan(FunctionType.X)``: the single annotation."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast

from flowspan.instrumentation.call_site import CallSite
from flowspan.instrumentation.handlers import HANDLERS
from flowspan.types import FunctionType


def flowspan[**P, R](function_type: FunctionType) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Mark a function with its role in an entry.

    ``FunctionType.ENTRY`` makes the function an entry, named after the
    function, with its own span. The other types record into the innermost
    entry and open no span. Outside an entry they just call the function.
    """

    if not isinstance(function_type, FunctionType):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"function_type must be a FunctionType, not {function_type!r}")
    handler = HANDLERS[function_type]

    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        if inspect.isgeneratorfunction(fn) or inspect.isasyncgenfunction(fn):
            raise TypeError("@flowspan does not support generator functions")
        call = CallSite(
            name=getattr(fn, "__name__", repr(fn)),
            qualname=getattr(fn, "__qualname__", repr(fn)),
            function_type=function_type,
        )

        if inspect.iscoroutinefunction(fn):
            coroutine_fn = cast(Callable[P, Awaitable[Any]], fn)

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                with handler.scope(call):
                    return await coroutine_fn(*args, **kwargs)

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with handler.scope(call):
                return fn(*args, **kwargs)

        return wrapper

    return decorate
