from __future__ import annotations

import asyncio
import inspect

import pytest

from flowspan import FunctionType, flowspan
from flowspan.telemetry import conventions
from tests._support import Spans


@flowspan(FunctionType.RULE)
def check(amount: int) -> int:
    return amount


@flowspan(FunctionType.HELPER)
def double(amount: int) -> int:
    return amount * 2


@flowspan(FunctionType.CLIENT)
def charge(amount: int) -> str:
    return f"charged {amount}"


@flowspan(FunctionType.ENTRY)
def place_order(amount: int) -> str:
    return charge(double(check(amount)))


def test_only_the_entry_opens_a_span(spans: Spans) -> None:
    assert place_order(5) == "charged 10"
    assert spans.names() == ["place_order"]


def test_entry_span_attributes(spans: Spans) -> None:
    place_order(1)
    assert spans.attributes("place_order") == {
        conventions.ENTRY_NAME: "place_order",
        conventions.FUNCTION_NAME: "place_order",
        conventions.FUNCTION_TYPE: "entry",
    }


def test_functions_outside_a_flow_only_call_through(spans: Spans) -> None:
    assert check(3) == 3
    assert charge(3) == "charged 3"
    assert spans.all() == []


def test_async_functions(spans: Spans) -> None:
    @flowspan(FunctionType.HELPER)
    async def fetch() -> str:
        await asyncio.sleep(0)
        return "ok"

    @flowspan(FunctionType.ENTRY)
    async def load() -> str:
        return await fetch()

    assert inspect.iscoroutinefunction(load)
    assert asyncio.run(load()) == "ok"
    assert spans.names() == ["load"]


def test_metadata_is_preserved() -> None:
    assert place_order.__name__ == "place_order"
    assert list(inspect.signature(place_order).parameters) == ["amount"]
    assert place_order.__wrapped__ is not None  # type: ignore[attr-defined]


def test_generators_are_rejected() -> None:
    def numbers() -> object:
        yield 1

    async def stream() -> object:
        yield 1

    with pytest.raises(TypeError, match="generator"):
        flowspan(FunctionType.RULE)(numbers)
    with pytest.raises(TypeError, match="generator"):
        flowspan(FunctionType.ENTRY)(stream)


def test_function_type_must_be_the_enum() -> None:
    with pytest.raises(TypeError, match="FunctionType"):
        flowspan("rule")  # type: ignore[arg-type]


def test_methods(spans: Spans) -> None:
    class Orders:
        @flowspan(FunctionType.ENTRY)
        def submit(self, amount: int) -> int:
            return self.price(amount)

        @staticmethod
        @flowspan(FunctionType.RULE)
        def price(amount: int) -> int:
            return amount + 1

    assert Orders().submit(1) == 2
    assert spans.attributes("submit")[conventions.FUNCTION_NAME].endswith("Orders.submit")
