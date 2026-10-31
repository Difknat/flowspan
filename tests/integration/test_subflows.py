from __future__ import annotations

import asyncio

import pytest

from flowspan import Decision, FunctionType, classify_as_expected, flowspan, record_exception
from tests._support import Spans

GATE = Decision("test_order_gate", {"accepted", "rejected"})
REFUND = Decision("test_refund_policy", {"full", "denied"})


class RefundWindowClosedError(Exception):
    pass


ENTRY = f"expected: refund: {__name__}.RefundWindowClosedError: refund window closed"


@pytest.fixture(autouse=True)
def _classify() -> None:
    classify_as_expected(RefundWindowClosedError)


@flowspan(FunctionType.ENTRY)
def refund(days: int) -> str:
    if days > 30:
        REFUND.record("denied", reason="past_30_days")
        raise RefundWindowClosedError("refund window closed")
    REFUND.record("full")
    return "refunded"


@flowspan(FunctionType.RULE)
def gate() -> None:
    GATE.record("accepted")


def test_sub_flow_has_its_own_span_and_evidence(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    def place_order() -> str:
        gate()
        return refund(1)

    assert place_order() == "refunded"
    child = spans.one("refund")
    assert child.parent is not None
    assert child.parent.span_id == spans.one("place_order").context.span_id
    assert spans.decisions("place_order") == ["test_order_gate: accepted"]
    assert spans.decisions("refund") == ["test_refund_policy: full"]


def test_exception_leaving_a_sub_flow_stays_on_the_sub_flow(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    def place_order() -> None:
        gate()
        refund(40)

    with pytest.raises(RefundWindowClosedError):
        place_order()
    assert spans.exceptions("refund") == [ENTRY]
    assert spans.decisions("refund") == ["test_refund_policy: denied: past_30_days"]
    assert spans.exceptions("place_order") == []
    assert spans.decisions("place_order") == ["test_order_gate: accepted"]


def test_parent_recording_a_sub_flow_exception_does_nothing(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    def place_order() -> str:
        try:
            refund(40)
        except RefundWindowClosedError as exc:
            record_exception(exc)
        return "handled"

    assert place_order() == "handled"
    assert spans.exceptions("refund") == [ENTRY]
    assert spans.exceptions("place_order") == []


def test_evidence_after_the_sub_flow_goes_to_the_parent(spans: Spans) -> None:
    @flowspan(FunctionType.HELPER)
    def audit() -> None:
        record_exception(RuntimeError("audit offline"))

    @flowspan(FunctionType.ENTRY)
    def place_order() -> None:
        refund(1)
        audit()

    place_order()
    assert spans.exceptions("place_order") == [
        f"unexpected: {audit.__qualname__}: RuntimeError: audit offline"
    ]
    assert spans.exceptions("refund") == []


def test_concurrent_async_sub_flows_stay_separate(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    async def settle(outcome: str) -> str:
        await asyncio.sleep(0)
        GATE.record(outcome)
        await asyncio.sleep(0)
        return outcome

    @flowspan(FunctionType.ENTRY)
    async def batch() -> list[str]:
        REFUND.record("full")
        return await asyncio.gather(settle("accepted"), settle("rejected"))

    assert asyncio.run(batch()) == ["accepted", "rejected"]
    settled = sorted(
        str((span.attributes or {})["flowspan.decisions"][0])  # type: ignore[index]
        for span in spans.all()
        if span.name == "settle"
    )
    assert settled == ["test_order_gate: accepted", "test_order_gate: rejected"]
    assert spans.decisions("batch") == ["test_refund_policy: full"]


def test_recursion_creates_nested_flows(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    def countdown(n: int) -> int:
        return 0 if n == 0 else countdown(n - 1)

    countdown(2)
    assert spans.names() == ["countdown", "countdown", "countdown"]


def test_each_root_flow_starts_empty(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    def failing() -> None:
        raise RuntimeError("once")

    @flowspan(FunctionType.ENTRY)
    def clean() -> str:
        return "ok"

    with pytest.raises(RuntimeError):
        failing()
    assert clean() == "ok"
    assert spans.exceptions("clean") == []
