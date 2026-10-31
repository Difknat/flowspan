"""Enums shared across Flowspan."""

from __future__ import annotations

from enum import StrEnum


class FunctionType(StrEnum):
    """The role a decorated function plays in an entry.

    ``ENTRY`` is an entry. It opens a span and owns the decisions and
    exceptions recorded while it runs. The other types record into the
    innermost entry and open no span.
    """

    ENTRY = "entry"
    RULE = "rule"
    HELPER = "helper"
    CLIENT = "client"


class ExceptionKind(StrEnum):
    """Whether an exception is an expected business outcome or a failure."""

    EXPECTED = "expected"
    UNEXPECTED = "unexpected"


class Outcome(StrEnum):
    """How a counted function call ended."""

    SUCCESS = "success"
    EXPECTED_EXCEPTION = "expected_exception"
    UNEXPECTED_EXCEPTION = "unexpected_exception"
