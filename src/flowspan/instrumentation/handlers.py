"""One handler per function type. The decorator picks one and enters its scope.

Handlers hold no state. Everything that varies per call lives in ContextVars,
so a single instance is safe across threads and asyncio tasks.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from types import MappingProxyType
from typing import Protocol

from flowspan.config import current_settings
from flowspan.context.scope import EntryScope, Frame, current_scope, push_frame, push_scope
from flowspan.evidence.exceptions import classify_exception, record_exception
from flowspan.instrumentation.call_site import CallSite
from flowspan.telemetry.instruments import count
from flowspan.telemetry.span_writer import entry_span, mark_failed, write_evidence
from flowspan.types import ExceptionKind, FunctionType, Outcome


class Handler(Protocol):
    def scope(self, call: CallSite) -> AbstractContextManager[None]: ...


class EntryHandler:
    """An entry: its own span and scope, written to the span when it ends."""

    @contextmanager
    def scope(self, call: CallSite) -> Generator[None]:
        with entry_span(call.name, call.qualname) as span:
            entry = EntryScope(name=call.name)
            with push_scope(entry), push_frame(Frame(call.qualname, FunctionType.ENTRY)):
                try:
                    yield
                except Exception as exc:
                    record_exception(exc)
                    if classify_exception(exc) is ExceptionKind.UNEXPECTED:
                        mark_failed(span, exc)
                    raise
                finally:
                    write_evidence(span, entry, current_settings().max_entry_bytes)


class FunctionHandler:
    """Rule, helper, and client calls: a frame and a counter, no span."""

    @contextmanager
    def scope(self, call: CallSite) -> Generator[None]:
        entry = current_scope()
        if entry is None:
            yield
            return
        with push_frame(Frame(call.qualname, call.function_type)):
            try:
                yield
            except Exception as exc:
                record_exception(exc)
                raise
            count(call.function_type, Outcome.SUCCESS, entry.name, call.qualname)


_FUNCTION = FunctionHandler()

HANDLERS: Mapping[FunctionType, Handler] = MappingProxyType(
    {
        FunctionType.ENTRY: EntryHandler(),
        FunctionType.RULE: _FUNCTION,
        FunctionType.HELPER: _FUNCTION,
        FunctionType.CLIENT: _FUNCTION,
    }
)

if set(HANDLERS) != set(FunctionType):  # pragma: no cover - guards future enum members
    raise RuntimeError("every FunctionType needs a handler")
