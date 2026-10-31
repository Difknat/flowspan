from __future__ import annotations

import pytest
from opentelemetry.trace import StatusCode

from flowspan import FunctionType, classify_as_expected, flowspan
from flowspan.instrumentation.handlers import HANDLERS, EntryHandler, FunctionHandler
from tests._support import Spans


class RejectedError(Exception):
    pass


def test_every_function_type_has_a_handler() -> None:
    assert set(HANDLERS) == set(FunctionType)
    assert isinstance(HANDLERS[FunctionType.ENTRY], EntryHandler)
    for function_type in (FunctionType.RULE, FunctionType.HELPER, FunctionType.CLIENT):
        assert isinstance(HANDLERS[function_type], FunctionHandler)


def test_status_is_error_only_for_unexpected(spans: Spans) -> None:
    classify_as_expected(RejectedError)

    @flowspan(FunctionType.ENTRY)
    def rejected() -> None:
        raise RejectedError("expected")

    @flowspan(FunctionType.ENTRY)
    def broken() -> None:
        raise RuntimeError("unexpected")

    with pytest.raises(RejectedError):
        rejected()
    with pytest.raises(RuntimeError):
        broken()

    assert spans.one("rejected").status.status_code is StatusCode.UNSET
    assert not spans.one("rejected").events
    failed = spans.one("broken")
    assert failed.status.status_code is StatusCode.ERROR
    assert failed.status.description == "RuntimeError: unexpected"
    assert [event.name for event in failed.events] == ["exception"]


def test_parent_status_reflects_an_exception_from_a_sub_flow(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    def child() -> None:
        raise RuntimeError("down")

    @flowspan(FunctionType.ENTRY)
    def parent() -> None:
        child()

    with pytest.raises(RuntimeError):
        parent()
    assert spans.one("child").status.status_code is StatusCode.ERROR
    assert spans.one("parent").status.status_code is StatusCode.ERROR
    assert spans.exceptions("parent") == []
