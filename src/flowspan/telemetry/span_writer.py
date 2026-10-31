"""Open an entry span and write an entry's evidence onto it."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry.trace import Span, Status, StatusCode

from flowspan.context.scope import EntryScope
from flowspan.telemetry import conventions
from flowspan.telemetry.formatting import decision_entry, exception_entry
from flowspan.telemetry.instruments import tracer
from flowspan.types import FunctionType


@contextmanager
def entry_span(name: str, qualname: str) -> Generator[Span]:
    """A span named after the entry. Flowspan, not OpenTelemetry, decides the status."""

    with tracer.start_as_current_span(
        name,
        attributes={
            conventions.ENTRY_NAME: name,
            conventions.FUNCTION_NAME: qualname,
            conventions.FUNCTION_TYPE: str(FunctionType.ENTRY),
        },
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        yield span


def mark_failed(span: Span, exc: BaseException) -> None:
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, f"{type(exc).__name__}: {exc}"))


def write_evidence(span: Span, scope: EntryScope, max_entry_bytes: int) -> None:
    """Write the entry's lists onto its span. Empty lists write nothing."""

    if scope.exceptions:
        span.set_attribute(
            conventions.EXCEPTIONS,
            [exception_entry(record, max_entry_bytes) for record in scope.exceptions],
        )
    if scope.decisions:
        span.set_attribute(
            conventions.DECISIONS, [decision_entry(record) for record in scope.decisions]
        )
