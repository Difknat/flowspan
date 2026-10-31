from __future__ import annotations

from enum import StrEnum

import pytest

from flowspan import Decision, FlowspanError, FunctionType, UnknownOutcomeError, flowspan
from tests._support import Spans


class Shipping(StrEnum):
    EXPRESS = "express"
    STANDARD = "standard"


SHIPPING = Decision("test_shipping", Shipping)
FRAUD = Decision("test_fraud_check", {"passed", "flagged"})


def test_handle_exposes_name_and_outcomes() -> None:
    assert SHIPPING.name == "test_shipping"
    assert SHIPPING.outcomes == frozenset({"express", "standard"})
    assert repr(FRAUD) == "Decision('test_fraud_check', ['flagged', 'passed'])"


def test_decisions_keep_call_order_and_full_reason(spans: Spans) -> None:
    reason = "r" * 5000

    @flowspan(FunctionType.RULE)
    def choose() -> None:
        FRAUD.record("flagged", reason=reason)
        SHIPPING.record(Shipping.EXPRESS)

    @flowspan(FunctionType.ENTRY)
    def place_order() -> None:
        choose()

    place_order()
    assert spans.decisions("place_order") == [
        f"test_fraud_check: flagged: {reason}",
        "test_shipping: express",
    ]


def test_record_outside_a_flow_does_nothing(spans: Spans) -> None:
    FRAUD.record("passed")
    assert spans.all() == []


def test_unknown_outcome_raises_even_outside_a_flow() -> None:
    with pytest.raises(UnknownOutcomeError, match="'maybe' is not an outcome"):
        FRAUD.record("maybe")
    assert issubclass(UnknownOutcomeError, FlowspanError)
    assert issubclass(UnknownOutcomeError, ValueError)


def test_same_definition_twice_gives_an_equal_handle() -> None:
    again = Decision("test_shipping", ["standard", "express"])
    assert again == SHIPPING
    assert hash(again) == hash(SHIPPING)
    assert again != FRAUD
    assert again != "test_shipping"


def test_invalid_definitions() -> None:
    with pytest.raises(ValueError, match="other outcomes"):
        Decision("test_shipping", {"express"})
    with pytest.raises(ValueError, match="empty"):
        Decision(" ", {"x"})
    with pytest.raises(ValueError, match="at least one outcome"):
        Decision("test_nothing", set[str]())
    with pytest.raises(TypeError, match="must be strings"):
        Decision("test_numbers", [1, 2])  # type: ignore[list-item]
