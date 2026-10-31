"""Build a sales insights report from a Parquet file and write it back to Parquet.

The job reads one row per sale, classifies each sale, and writes one row per
region and product. Revenue and units sold count completed sales only.
Refunded and cancelled sales still count as orders.

Run ``python build_report.py`` after ``pip install -r requirements.txt`` and
``docker compose up -d``. The application owns its exception types, its
decisions, and the OpenTelemetry SDK. Flowspan only records.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

import pyarrow as pa
import pyarrow.parquet as pq

from flowspan import (
    Decision,
    FunctionType,
    classify_as_expected,
    classify_as_unexpected,
    flowspan,
    record_exception,
)

_STATUSES = frozenset({"completed", "refunded", "cancelled"})
_OTLP_BASE = "http://localhost:5080/api/default"


class InvalidSaleError(Exception):
    """A row that is not a sale. The report skips it."""


class EmptyReportError(Exception):
    """The report has no completed sales, so there is nothing to publish."""


classify_as_unexpected(InvalidSaleError)
classify_as_expected(EmptyReportError)

CLASSIFIED_SALE = Decision("classified_sale", _STATUSES)
ACCEPTED_REPORT = Decision("accepted_report", {"published", "empty"})


class SaleRow(TypedDict):
    order_id: str
    region: str
    product: str
    units: int
    unit_price: float
    status: str


@dataclass(frozen=True, slots=True)
class Sale:
    order_id: str
    region: str
    product: str
    units: int
    unit_price: float
    status: str


@dataclass(frozen=True, slots=True)
class Insight:
    region: str
    product: str
    orders: int
    units_sold: int
    revenue: float


@dataclass(frozen=True, slots=True)
class Report:
    insights: tuple[Insight, ...]
    completed_orders: int


def write_sales(path: Path, rows: list[SaleRow]) -> None:
    """Write sale rows to ``path``. Used by the sample file and by tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(list(rows), schema=_SALES_SCHEMA)
    pq.write_table(table, path)


def ensure_sample(path: Path) -> None:
    """Create a small sales file when ``path`` does not exist yet."""

    if path.exists():
        return
    write_sales(
        path,
        [
            _sale("1001", "north", "tea", 2, 5.0, "completed"),
            _sale("1002", "north", "tea", 1, 5.0, "refunded"),
            _sale("1003", "south", "mug", 3, 4.0, "cancelled"),
            _sale("1004", "south", "mug", 4, 4.0, "completed"),
            _sale("1005", "north", "tea", 1, -1.0, "completed"),
        ],
    )


@flowspan(FunctionType.HELPER)
def read_sales(path: Path) -> list[SaleRow]:
    return [cast(SaleRow, row) for row in pq.read_table(path).to_pylist()]


@flowspan(FunctionType.RULE)
def classify_sale(row: SaleRow) -> Sale:
    status = row["status"]
    units = row["units"]
    price = row["unit_price"]
    if status not in _STATUSES or units < 0 or price < 0:
        raise InvalidSaleError(f"{row['order_id']}: status {status}, price {price}, units {units}")
    CLASSIFIED_SALE.record(status)
    return Sale(
        order_id=str(row["order_id"]),
        region=str(row["region"]),
        product=str(row["product"]),
        units=units,
        unit_price=price,
        status=status,
    )


@flowspan(FunctionType.RULE)
def aggregate(rows: list[SaleRow]) -> Report:
    totals: dict[tuple[str, str], Insight] = {}
    completed = 0
    for row in rows:
        try:
            sale = classify_sale(row)
        except InvalidSaleError as exc:
            record_exception(exc)
            continue
        key = (sale.region, sale.product)
        current = totals.get(key, Insight(sale.region, sale.product, 0, 0, 0.0))
        sold = sale.units if sale.status == "completed" else 0
        revenue = sale.units * sale.unit_price if sale.status == "completed" else 0.0
        if sale.status == "completed":
            completed += 1
        totals[key] = Insight(
            sale.region,
            sale.product,
            current.orders + 1,
            current.units_sold + sold,
            current.revenue + revenue,
        )
    insights = tuple(sorted(totals.values(), key=lambda item: (item.region, item.product)))
    return Report(insights, completed)


@flowspan(FunctionType.HELPER)
def write_report(insights: tuple[Insight, ...], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "region": item.region,
            "product": item.product,
            "orders": item.orders,
            "units_sold": item.units_sold,
            "revenue": item.revenue,
        }
        for item in insights
    ]
    table = pa.Table.from_pylist(rows, schema=_INSIGHTS_SCHEMA)
    pq.write_table(table, path)


@flowspan(FunctionType.ENTRY)
def publish_report(report: Report, path: Path) -> None:
    if report.completed_orders == 0:
        ACCEPTED_REPORT.record("empty")
        raise EmptyReportError("no completed sales")
    ACCEPTED_REPORT.record("published")
    write_report(report.insights, path)


@flowspan(FunctionType.ENTRY)
def build_report(sales_path: Path, report_path: Path) -> Report:
    report = aggregate(read_sales(sales_path))
    publish_report(report, report_path)
    return report


_SALES_SCHEMA = pa.schema(
    [
        ("order_id", pa.string()),
        ("region", pa.string()),
        ("product", pa.string()),
        ("units", pa.int64()),
        ("unit_price", pa.float64()),
        ("status", pa.string()),
    ]
)
_INSIGHTS_SCHEMA = pa.schema(
    [
        ("region", pa.string()),
        ("product", pa.string()),
        ("orders", pa.int64()),
        ("units_sold", pa.int64()),
        ("revenue", pa.float64()),
    ]
)


def _sale(
    order_id: str, region: str, product: str, units: int, unit_price: float, status: str
) -> SaleRow:
    return {
        "order_id": order_id,
        "region": region,
        "product": product,
        "units": units,
        "unit_price": unit_price,
        "status": status,
    }


def main() -> None:
    data = Path(__file__).parent / "data"
    sales_path = data / "sales.parquet"
    report_path = data / "insights.parquet"
    ensure_sample(sales_path)
    tracer_provider, meter_provider = _install_telemetry()
    try:
        report = build_report(sales_path, report_path)
    finally:
        _shutdown(tracer_provider, meter_provider)
    for item in report.insights:
        print(f"{item.region} {item.product}: {item.orders} orders, revenue {item.revenue}")


def _install_telemetry() -> tuple[object, object]:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    email = os.environ.get("OPENOBSERVE_EMAIL", "root@example.com")
    password = os.environ.get("OPENOBSERVE_PASSWORD", "Complexpass#123")
    base = os.environ.get("OPENOBSERVE_OTLP_ENDPOINT", _OTLP_BASE).rstrip("/")
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {token}"}
    resource = Resource.create({"service.name": "sales-report"})

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=headers, timeout=2)
        )
    )
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{base}/v1/metrics", headers=headers, timeout=2),
        export_interval_millis=1000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)
    return tracer_provider, meter_provider


def _shutdown(tracer_provider: object, meter_provider: object) -> None:
    for provider in (tracer_provider, meter_provider):
        try:
            provider.shutdown()  # type: ignore[attr-defined]
        except Exception as exc:
            print(f"telemetry export failed: {exc}")


if __name__ == "__main__":
    main()
