from __future__ import annotations

import asyncio
import contextlib

import pytest

from flowspan import FunctionType, classify_as_expected, flowspan, record_exception
from tests._support import Spans

MODULE = __name__


class OutOfStockError(LookupError):
    pass


class GatewayError(LookupError):
    pass


def test_propagating_exceptions_are_attributed_to_the_raising_function(spans: Spans) -> None:
    classify_as_expected(OutOfStockError)

    @flowspan(FunctionType.RULE)
    def reserve() -> None:
        raise OutOfStockError("sku-1")

    @flowspan(FunctionType.CLIENT)
    def call_gateway() -> None:
        raise GatewayError("timeout")

    @flowspan(FunctionType.ENTRY)
    def place_order() -> None:
        with contextlib.suppress(OutOfStockError):
            reserve()
        call_gateway()

    with pytest.raises(GatewayError):
        place_order()
    assert spans.exceptions("place_order") == [
        f"expected: {reserve.__qualname__}: {MODULE}.OutOfStockError: sku-1",
        f"unexpected: {call_gateway.__qualname__}: {MODULE}.GatewayError: timeout",
    ]


def test_builtin_types_have_no_module_prefix(spans: Spans) -> None:
    @flowspan(FunctionType.ENTRY)
    def parse() -> None:
        int("x")

    with pytest.raises(ValueError, match="invalid literal"):
        parse()
    assert spans.exceptions("parse")[0].startswith(f"unexpected: {parse.__qualname__}: ValueError:")


def test_exception_passing_through_many_functions_is_recorded_once(spans: Spans) -> None:
    @flowspan(FunctionType.CLIENT)
    def http() -> None:
        raise GatewayError("down")

    @flowspan(FunctionType.CLIENT)
    def accessor() -> None:
        http()

    @flowspan(FunctionType.RULE)
    def service() -> None:
        accessor()

    @flowspan(FunctionType.ENTRY)
    def load() -> None:
        service()

    with pytest.raises(GatewayError):
        load()
    assert spans.exceptions("load") == [
        f"unexpected: {http.__qualname__}: {MODULE}.GatewayError: down"
    ]


def test_caught_exception_is_attributed_to_the_catching_function(spans: Spans) -> None:
    @flowspan(FunctionType.HELPER)
    def lookup() -> str:
        try:
            raise GatewayError("cache miss")
        except GatewayError as exc:
            record_exception(exc)
        return "fallback"

    @flowspan(FunctionType.ENTRY)
    def load() -> str:
        return lookup()

    assert load() == "fallback"
    assert spans.exceptions("load") == [
        f"unexpected: {lookup.__qualname__}: {MODULE}.GatewayError: cache miss"
    ]


def test_recording_the_same_object_twice_keeps_one_entry(spans: Spans) -> None:
    error = GatewayError("duplicate")

    @flowspan(FunctionType.ENTRY)
    def load() -> None:
        record_exception(error)
        record_exception(error)

    load()
    assert len(spans.exceptions("load")) == 1


def test_outside_a_flow_nothing_is_recorded(spans: Spans) -> None:
    record_exception(GatewayError("nowhere"))
    assert spans.all() == []


def test_cancellation_and_interrupts_are_not_recorded(spans: Spans) -> None:
    @flowspan(FunctionType.CLIENT)
    async def wait_forever() -> None:
        await asyncio.sleep(10)

    @flowspan(FunctionType.ENTRY)
    async def sync_orders() -> None:
        record_exception(KeyboardInterrupt())
        await wait_forever()

    async def main() -> None:
        task = asyncio.create_task(sync_orders())
        await asyncio.sleep(0)
        task.cancel()
        await task

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main())
    assert spans.names() == ["sync_orders"]
    assert spans.exceptions("sync_orders") == []
