"""Classify client exception types and record exceptions into the innermost entry."""

from __future__ import annotations

from flowspan.config import current_settings
from flowspan.context.records import ExceptionRecord
from flowspan.context.scope import already_seen, current_frame, current_scope
from flowspan.evidence.classification import classify
from flowspan.telemetry.formatting import qualified_type_name
from flowspan.telemetry.instruments import count
from flowspan.types import ExceptionKind, FunctionType, Outcome


def classify_as_expected(*exc_types: type[BaseException]) -> None:
    """Treat these types, and their subclasses, as expected business outcomes."""

    current_settings().types.register(ExceptionKind.EXPECTED, *exc_types)


def classify_as_unexpected(*exc_types: type[BaseException]) -> None:
    """Treat these types, and their subclasses, as failures. This is also the default."""

    current_settings().types.register(ExceptionKind.UNEXPECTED, *exc_types)


def classify_exception(exc: BaseException) -> ExceptionKind:
    settings = current_settings()
    return classify(exc, settings.classifier, settings.types)


def record_exception(exc: BaseException) -> None:
    """Record ``exc`` on the innermost active entry.

    Use it for an exception your code catches and does not re-raise. Exceptions
    that propagate out of a decorated function are recorded automatically.
    Each exception object is recorded once across all nested entries. Outside an
    entry this does nothing. Interrupts and cancellation are never recorded.
    """

    if not isinstance(exc, Exception):
        return
    scope = current_scope()
    if scope is None or already_seen(exc):
        return
    scope.seen[id(exc)] = exc

    frame = current_frame()
    function_name = frame.qualname if frame is not None else scope.name
    function_type = frame.function_type if frame is not None else FunctionType.ENTRY
    kind = classify_exception(exc)
    scope.exceptions.append(
        ExceptionRecord(
            kind=kind,
            exc_type=qualified_type_name(exc),
            message=str(exc),
            function_name=function_name,
        )
    )
    outcome = (
        Outcome.EXPECTED_EXCEPTION
        if kind is ExceptionKind.EXPECTED
        else Outcome.UNEXPECTED_EXCEPTION
    )
    count(function_type, outcome, scope.name, function_name)
