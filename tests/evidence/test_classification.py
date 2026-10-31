from __future__ import annotations

import pytest

from flowspan import ExceptionKind, classify_as_expected, classify_as_unexpected, configure
from flowspan.evidence.classification import TypeRegistry, classify
from flowspan.evidence.exceptions import classify_exception


class LookupFailedError(LookupError):
    pass


class OutOfStockError(LookupFailedError):
    pass


def test_unregistered_exceptions_are_unexpected() -> None:
    assert classify_exception(ValueError()) is ExceptionKind.UNEXPECTED


def test_registered_types_and_subclasses() -> None:
    classify_as_expected(LookupFailedError, KeyError)
    assert classify_exception(LookupFailedError()) is ExceptionKind.EXPECTED
    assert classify_exception(OutOfStockError()) is ExceptionKind.EXPECTED
    assert classify_exception(KeyError()) is ExceptionKind.EXPECTED


def test_nearest_registered_base_wins() -> None:
    classify_as_expected(LookupFailedError)
    classify_as_unexpected(OutOfStockError)
    assert classify_exception(LookupFailedError()) is ExceptionKind.EXPECTED
    assert classify_exception(OutOfStockError()) is ExceptionKind.UNEXPECTED


def test_registering_again_changes_the_kind() -> None:
    classify_as_expected(LookupFailedError)
    classify_as_unexpected(LookupFailedError)
    assert classify_exception(LookupFailedError()) is ExceptionKind.UNEXPECTED


def test_only_exception_types_can_be_registered() -> None:
    with pytest.raises(TypeError, match="exception type"):
        classify_as_expected(int)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="exception type"):
        classify_as_expected(ValueError())  # type: ignore[arg-type]


def test_classifier_runs_before_the_registry() -> None:
    classify_as_unexpected(LookupFailedError)
    configure(classifier=lambda exc: ExceptionKind.EXPECTED if "expected" in str(exc) else None)
    assert classify_exception(LookupFailedError("expected")) is ExceptionKind.EXPECTED
    assert classify_exception(LookupFailedError("other")) is ExceptionKind.UNEXPECTED


def test_a_failing_classifier_falls_back_to_the_registry() -> None:
    def broken(exc: BaseException) -> ExceptionKind | None:
        raise RuntimeError("classifier bug")

    classify_as_expected(LookupFailedError)
    configure(classifier=broken)
    assert classify_exception(LookupFailedError()) is ExceptionKind.EXPECTED


def test_registries_are_independent() -> None:
    first, second = TypeRegistry(), TypeRegistry()
    first.register(ExceptionKind.EXPECTED, LookupFailedError)
    assert classify(LookupFailedError(), None, first) is ExceptionKind.EXPECTED
    assert classify(LookupFailedError(), None, second) is ExceptionKind.UNEXPECTED
