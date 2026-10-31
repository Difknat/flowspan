from __future__ import annotations

import contextlib

import pytest

from flowspan import FunctionType, classify_as_expected, flowspan
from tests._support import Call, Calls


class SoldOutError(Exception):
    pass


def test_one_counter_split_by_type_and_outcome(calls: Calls) -> None:
    classify_as_expected(SoldOutError)

    @flowspan(FunctionType.RULE)
    def price() -> int:
        return 1

    @flowspan(FunctionType.HELPER)
    def parse() -> None:
        raise ValueError("bad row")

    @flowspan(FunctionType.CLIENT)
    def reserve() -> None:
        raise SoldOutError("sold out")

    @flowspan(FunctionType.ENTRY)
    def place_order() -> int:
        for step in (parse, reserve):
            with contextlib.suppress(ValueError, SoldOutError):
                step()
        return price()

    place_order()
    assert sorted(calls.collect(), key=lambda call: call.function) == sorted(
        [
            Call("place_order", price.__qualname__, "rule", "success", 1),
            Call("place_order", parse.__qualname__, "helper", "unexpected_exception", 1),
            Call("place_order", reserve.__qualname__, "client", "expected_exception", 1),
        ],
        key=lambda call: call.function,
    )


def test_entries_and_calls_outside_an_entry_are_not_counted(calls: Calls) -> None:
    @flowspan(FunctionType.RULE)
    def check() -> None:
        return None

    @flowspan(FunctionType.ENTRY)
    def place_order() -> None:
        raise SoldOutError("no")

    check()
    with pytest.raises(SoldOutError):
        place_order()
    assert calls.collect() == []


def test_nested_clients_count_once_per_function(calls: Calls) -> None:
    @flowspan(FunctionType.CLIENT)
    def http() -> str:
        return "body"

    @flowspan(FunctionType.CLIENT)
    def accessor() -> str:
        return http()

    @flowspan(FunctionType.ENTRY)
    def load() -> str:
        return accessor()

    load()
    assert {call.function for call in calls.collect()} == {http.__qualname__, accessor.__qualname__}


def test_propagating_exception_is_counted_once(calls: Calls) -> None:
    @flowspan(FunctionType.CLIENT)
    def http() -> None:
        raise ValueError("down")

    @flowspan(FunctionType.CLIENT)
    def accessor() -> None:
        http()

    @flowspan(FunctionType.ENTRY)
    def load() -> None:
        accessor()

    with pytest.raises(ValueError, match="down"):
        load()
    assert calls.collect() == [Call("load", http.__qualname__, "client", "unexpected_exception", 1)]


def test_flow_attribute_is_the_innermost_flow(calls: Calls) -> None:
    @flowspan(FunctionType.RULE)
    def check() -> None:
        return None

    @flowspan(FunctionType.ENTRY)
    def refund() -> None:
        check()

    @flowspan(FunctionType.ENTRY)
    def place_order() -> None:
        refund()

    place_order()
    (call,) = calls.collect()
    assert call.flow == "refund"
