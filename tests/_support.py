"""Test helpers. The OpenTelemetry SDK is installed here, as an application would."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import Counter, MeterProvider
from opentelemetry.sdk.metrics.export import AggregationTemporality, InMemoryMetricReader
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from flowspan.telemetry import conventions

EXPORTER = InMemorySpanExporter()
READER = InMemoryMetricReader(preferred_temporality={Counter: AggregationTemporality.DELTA})


def install_sdk() -> None:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
    trace.set_tracer_provider(provider)
    metrics.set_meter_provider(MeterProvider(metric_readers=[READER]))


class Spans:
    def all(self) -> list[ReadableSpan]:
        return list(EXPORTER.get_finished_spans())

    def names(self) -> list[str]:
        return [span.name for span in self.all()]

    def one(self, name: str) -> ReadableSpan:
        found = [span for span in self.all() if span.name == name]
        assert len(found) == 1, f"expected one {name!r} span, got {len(found)}"
        return found[0]

    def attributes(self, name: str) -> dict[str, Any]:
        return dict(self.one(name).attributes or {})

    def exceptions(self, name: str) -> list[str]:
        return _strings(self.attributes(name).get(conventions.EXCEPTIONS))

    def decisions(self, name: str) -> list[str]:
        return _strings(self.attributes(name).get(conventions.DECISIONS))


@dataclass(frozen=True)
class Call:
    flow: str
    function: str
    function_type: str
    outcome: str
    value: int


class Calls:
    """Points of ``flowspan.function.calls`` collected since the last read."""

    def collect(self) -> list[Call]:
        data = READER.get_metrics_data()
        calls: list[Call] = []
        if data is None:
            return calls
        for resource in data.resource_metrics:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    assert metric.name == conventions.CALLS_METRIC
                    for point in metric.data.data_points:
                        value = int(getattr(point, "value", 0))
                        if value:
                            calls.append(_call(dict(point.attributes or {}), value))
        return calls


def _call(attributes: dict[str, Any], value: int) -> Call:
    assert set(attributes) == {
        conventions.ENTRY_NAME,
        conventions.FUNCTION_NAME,
        conventions.FUNCTION_TYPE,
        conventions.OUTCOME,
    }
    return Call(
        flow=attributes[conventions.ENTRY_NAME],
        function=attributes[conventions.FUNCTION_NAME],
        function_type=attributes[conventions.FUNCTION_TYPE],
        outcome=attributes[conventions.OUTCOME],
        value=value,
    )


def _strings(value: Sequence[Any] | None) -> list[str]:
    return [] if value is None else [str(item) for item in value]
