from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pyarrow.parquet as pq

from tests._support import Spans

_EXAMPLE = Path(__file__).parents[2] / "examples" / "sales_report" / "build_report.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sales_report_build", _EXAMPLE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_report_records_decisions_and_skips_an_invalid_row(tmp_path: Path, spans: Spans) -> None:
    job = _load()
    job.classify_as_expected(job.EmptyReportError)
    job.classify_as_unexpected(job.InvalidSaleError)
    sales = tmp_path / "sales.parquet"
    report = tmp_path / "insights.parquet"
    job.write_sales(
        sales,
        [
            job._sale("1", "north", "tea", 2, 5.0, "completed"),
            job._sale("2", "north", "tea", 1, 5.0, "refunded"),
            job._sale("3", "south", "mug", 3, 4.0, "cancelled"),
            job._sale("4", "south", "mug", 4, 4.0, "completed"),
            job._sale("5", "north", "tea", 1, -1.0, "completed"),
        ],
    )

    built = job.build_report(sales, report)

    rows = [
        (item.region, item.product, item.orders, item.units_sold, item.revenue)
        for item in built.insights
    ]
    assert rows == [
        ("north", "tea", 2, 2, 10.0),
        ("south", "mug", 2, 4, 16.0),
    ]
    assert pq.read_table(report).to_pylist() == [
        {"region": "north", "product": "tea", "orders": 2, "units_sold": 2, "revenue": 10.0},
        {"region": "south", "product": "mug", "orders": 2, "units_sold": 4, "revenue": 16.0},
    ]
    assert spans.decisions("build_report") == [
        "classified_sale: completed",
        "classified_sale: refunded",
        "classified_sale: cancelled",
        "classified_sale: completed",
    ]
    assert spans.decisions("publish_report") == ["accepted_report: published"]
    assert spans.exceptions("publish_report") == []
    (entry,) = spans.exceptions("build_report")
    assert entry.startswith("unexpected: classify_sale: ")
    assert "InvalidSaleError: 5:" in entry
    child = spans.one("publish_report")
    assert child.parent is not None
    assert child.parent.span_id == spans.one("build_report").context.span_id
