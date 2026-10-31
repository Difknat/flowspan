from __future__ import annotations

import pytest

from flowspan import FunctionType, Settings, configure, flowspan
from flowspan.config import MIN_ENTRY_BYTES, current_settings
from flowspan.context.records import DecisionRecord, ExceptionRecord
from flowspan.telemetry.formatting import TRUNCATED, cap, decision_entry, exception_entry
from flowspan.types import ExceptionKind
from tests._support import Spans


def test_entries() -> None:
    record = ExceptionRecord(ExceptionKind.EXPECTED, "app.Rejected", "too small", "gate")
    assert exception_entry(record, 2048) == "expected: gate: app.Rejected: too small"
    assert decision_entry(DecisionRecord("gate", "rejected")) == "gate: rejected"
    assert decision_entry(DecisionRecord("gate", "rejected", "low")) == "gate: rejected: low"


def test_cap_never_splits_a_character() -> None:
    capped = cap("é" * 100, 64)
    assert capped.endswith(TRUNCATED)
    assert len(capped.encode("utf-8")) <= 64
    assert cap("short", 64) == "short"


def test_configured_limit_applies_to_span_entries(spans: Spans) -> None:
    configure(max_entry_bytes=100)

    @flowspan(FunctionType.ENTRY)
    def load() -> None:
        raise RuntimeError("x" * 500)

    with pytest.raises(RuntimeError):
        load()
    (entry,) = spans.exceptions("load")
    assert entry.endswith(TRUNCATED)
    assert len(entry.encode("utf-8")) <= 100


def test_configure_replaces_only_the_given_settings() -> None:
    before = current_settings()
    after = configure(max_entry_bytes=512)
    assert after is current_settings()
    assert after.max_entry_bytes == 512
    assert after.types is before.types
    assert after.classifier is before.classifier


def test_settings_are_validated_and_frozen() -> None:
    with pytest.raises(ValueError, match="at least"):
        configure(max_entry_bytes=MIN_ENTRY_BYTES - 1)
    with pytest.raises(AttributeError):
        Settings().max_entry_bytes = 10  # type: ignore[misc]
