"""Immutable evidence records collected by an entry."""

from __future__ import annotations

from dataclasses import dataclass

from flowspan.types import ExceptionKind


@dataclass(frozen=True, slots=True)
class ExceptionRecord:
    kind: ExceptionKind
    exc_type: str
    message: str
    function_name: str


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    name: str
    outcome: str
    reason: str | None = None
