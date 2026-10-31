from __future__ import annotations

from collections.abc import Iterator

import pytest

from flowspan import configure
from flowspan.evidence.classification import TypeRegistry
from tests._support import EXPORTER, READER, Calls, Spans, install_sdk

install_sdk()


@pytest.fixture(autouse=True)
def _isolate() -> Iterator[None]:
    EXPORTER.clear()
    READER.get_metrics_data()
    yield
    EXPORTER.clear()
    configure(classifier=None, max_entry_bytes=2048, types=TypeRegistry())


@pytest.fixture
def spans() -> Spans:
    return Spans()


@pytest.fixture
def calls() -> Calls:
    return Calls()
