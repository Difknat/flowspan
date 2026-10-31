"""Flowspan records what happened in an entry.

Mark the entry point and its nested entries with ``@flowspan(FunctionType.ENTRY)`` and
the functions under them with ``RULE``, ``HELPER``, or ``CLIENT``.
Each entry gets one span that carries its decisions and exceptions.
"""

from flowspan._version import __version__
from flowspan.config import Settings, configure
from flowspan.errors import FlowspanError, UnknownOutcomeError
from flowspan.evidence.decisions import Decision
from flowspan.evidence.exceptions import (
    classify_as_expected,
    classify_as_unexpected,
    record_exception,
)
from flowspan.instrumentation.decorator import flowspan
from flowspan.types import ExceptionKind, FunctionType

__all__ = [
    "Decision",
    "ExceptionKind",
    "FlowspanError",
    "FunctionType",
    "Settings",
    "UnknownOutcomeError",
    "__version__",
    "classify_as_expected",
    "classify_as_unexpected",
    "configure",
    "flowspan",
    "record_exception",
]
