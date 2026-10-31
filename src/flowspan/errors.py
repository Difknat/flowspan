"""Errors raised by Flowspan itself. Client exceptions are never defined here."""

from __future__ import annotations


class FlowspanError(Exception):
    """Base class for errors raised by Flowspan."""


class UnknownOutcomeError(FlowspanError, ValueError):
    """A decision was recorded with an outcome it does not declare."""
