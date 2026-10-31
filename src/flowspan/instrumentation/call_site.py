from __future__ import annotations

from dataclasses import dataclass

from flowspan.types import FunctionType


@dataclass(frozen=True, slots=True)
class CallSite:
    """What is fixed about a decorated function, computed once at decoration time."""

    name: str
    qualname: str
    function_type: FunctionType
