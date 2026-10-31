from __future__ import annotations

import subprocess
import sys

import flowspan


def test_import_does_not_load_the_sdk() -> None:
    script = (
        "import sys, flowspan\n"
        "loaded = [m for m in sys.modules if m.startswith(('opentelemetry.sdk', "
        "'opentelemetry.exporter'))]\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_public_api() -> None:
    assert sorted(flowspan.__all__) == [
        "Decision",
        "ExceptionKind",
        "FlowspanError",
        "FunctionType",
        "Settings",
        "UnknownOutcomeError",
        "__version__",
        "classify_as_expected",
        "classify_as_unexpected",
        "configure",
        "flowspan",
        "record_exception",
    ]
    assert flowspan.__version__
