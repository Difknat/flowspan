"""The stack of active entries and the function frames inside them.

Each ContextVar holds an immutable tuple, so a token restores the previous
stack exactly. The ``EntryScope`` objects inside are mutable, so asyncio tasks
started inside an entry append to that entry's lists.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from flowspan.context.records import DecisionRecord, ExceptionRecord
from flowspan.types import FunctionType


@dataclass(frozen=True, slots=True)
class Frame:
    qualname: str
    function_type: FunctionType


@dataclass(slots=True)
class EntryScope:
    """Evidence collected by one entry.

    ``seen`` keeps a reference to each recorded exception so its id cannot be
    reused by another object while the entry is running.
    """

    name: str
    exceptions: list[ExceptionRecord] = field(default_factory=list[ExceptionRecord])
    decisions: list[DecisionRecord] = field(default_factory=list[DecisionRecord])
    seen: dict[int, BaseException] = field(default_factory=dict[int, BaseException])


_SCOPES: ContextVar[tuple[EntryScope, ...]] = ContextVar("flowspan_scopes", default=())
_FRAMES: ContextVar[tuple[Frame, ...]] = ContextVar("flowspan_frames", default=())


def current_scope() -> EntryScope | None:
    scopes = _SCOPES.get()
    return scopes[-1] if scopes else None


def current_frame() -> Frame | None:
    frames = _FRAMES.get()
    return frames[-1] if frames else None


def already_seen(exc: BaseException) -> bool:
    return any(id(exc) in scope.seen for scope in _SCOPES.get())


@contextmanager
def push_scope(scope: EntryScope) -> Generator[EntryScope]:
    """Make ``scope`` the innermost entry. On exit its seen exceptions pass to the parent."""

    token = _SCOPES.set((*_SCOPES.get(), scope))
    try:
        yield scope
    finally:
        _SCOPES.reset(token)
        parent = current_scope()
        if parent is not None:
            parent.seen.update(scope.seen)


@contextmanager
def push_frame(frame: Frame) -> Generator[Frame]:
    token = _FRAMES.set((*_FRAMES.get(), frame))
    try:
        yield frame
    finally:
        _FRAMES.reset(token)
