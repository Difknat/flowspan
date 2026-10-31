from __future__ import annotations

import pytest

from flowspan.context.scope import (
    EntryScope,
    Frame,
    already_seen,
    current_frame,
    current_scope,
    push_frame,
    push_scope,
)
from flowspan.types import FunctionType


def test_nothing_is_active_by_default() -> None:
    assert current_scope() is None
    assert current_frame() is None


def test_push_and_pop_restore_the_previous_stack() -> None:
    outer, inner = EntryScope("outer"), EntryScope("inner")
    with push_scope(outer):
        with push_scope(inner):
            assert current_scope() is inner
        assert current_scope() is outer
    assert current_scope() is None


def test_stack_is_restored_when_the_body_raises() -> None:
    frame = Frame("f", FunctionType.RULE)
    seen: list[Frame | None] = []

    def fail() -> None:
        with push_frame(frame):
            seen.append(current_frame())
            raise RuntimeError

    with pytest.raises(RuntimeError):
        fail()
    assert seen == [frame]
    assert current_frame() is None


def test_seen_exceptions_pass_to_the_parent() -> None:
    error = ValueError()
    outer, inner = EntryScope("outer"), EntryScope("inner")
    with push_scope(outer):
        with push_scope(inner):
            inner.seen[id(error)] = error
            assert already_seen(error)
        assert outer.seen == {id(error): error}
        assert already_seen(error)
    assert not already_seen(error)
