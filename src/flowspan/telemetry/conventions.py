"""Every span attribute and metric name Flowspan emits.

Flowspan-specific names live under the ``flowspan.`` namespace. ``code.function.name``
is the OpenTelemetry semantic convention for the function's qualified name.
"""

from __future__ import annotations

from typing import Final

INSTRUMENTATION_SCOPE: Final = "flowspan"

ENTRY_NAME: Final = "flowspan.entry.name"
FUNCTION_NAME: Final = "code.function.name"
FUNCTION_TYPE: Final = "flowspan.function.type"
DECISIONS: Final = "flowspan.decisions"
EXCEPTIONS: Final = "flowspan.exceptions"
OUTCOME: Final = "flowspan.outcome"

CALLS_METRIC: Final = "flowspan.function.calls"
CALLS_UNIT: Final = "{call}"
CALLS_DESCRIPTION: Final = "Calls to rule, helper, and client functions inside an entry"
