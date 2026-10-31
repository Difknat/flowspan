"""The tracer and the calls counter, obtained from the OpenTelemetry API.

The API hands out proxies, so these start recording as soon as the
application installs an SDK provider, even after ``import flowspan``.
"""

from __future__ import annotations

from opentelemetry import metrics, trace

from flowspan._version import __version__
from flowspan.telemetry import conventions
from flowspan.types import FunctionType, Outcome

tracer = trace.get_tracer(conventions.INSTRUMENTATION_SCOPE, __version__)
_meter = metrics.get_meter(conventions.INSTRUMENTATION_SCOPE, __version__)
_calls = _meter.create_counter(
    conventions.CALLS_METRIC,
    unit=conventions.CALLS_UNIT,
    description=conventions.CALLS_DESCRIPTION,
)


def count(function_type: FunctionType, outcome: Outcome, entry: str, function_name: str) -> None:
    """Add one call. Entries are measured by their spans and are not counted."""

    if function_type is FunctionType.ENTRY:
        return
    _calls.add(
        1,
        {
            conventions.ENTRY_NAME: entry,
            conventions.FUNCTION_NAME: function_name,
            conventions.FUNCTION_TYPE: str(function_type),
            conventions.OUTCOME: str(outcome),
        },
    )
