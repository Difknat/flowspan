"""``Decision``: a typed handle for one business decision and its outcomes."""

from __future__ import annotations

import threading
from collections.abc import Iterable
from enum import Enum
from typing import cast, overload

from flowspan.context.records import DecisionRecord
from flowspan.context.scope import current_scope
from flowspan.errors import UnknownOutcomeError

_REGISTRY: dict[str, frozenset[str]] = {}
_LOCK = threading.Lock()


class Decision[O: str]:
    """A named decision with a fixed set of outcomes.

    Define it once at module level, from a ``StrEnum`` or from strings, then
    call ``record`` at the branch where the decision is made::

        class RefundPolicy(StrEnum):
            FULL = "full"
            DENIED = "denied"

        REFUND = Decision("refund_policy", RefundPolicy)
        REFUND.record(RefundPolicy.DENIED, reason="past_30_days")

    Names are unique per process. Defining the same name with the same
    outcomes again is allowed; different outcomes raise ``ValueError``.
    """

    __slots__ = ("_name", "_outcomes")

    @overload
    def __init__(self, name: str, outcomes: type[O]) -> None: ...
    @overload
    def __init__(self: Decision[str], name: str, outcomes: Iterable[str]) -> None: ...

    def __init__(self, name: str, outcomes: type[O] | Iterable[str]) -> None:
        if not name.strip():
            raise ValueError("decision name must not be empty")
        members = cast(Iterable[object], outcomes)
        allowed = frozenset(_value(outcome) for outcome in members)
        if not allowed:
            raise ValueError(f"decision {name!r} needs at least one outcome")
        with _LOCK:
            existing = _REGISTRY.setdefault(name, allowed)
        if existing != allowed:
            raise ValueError(f"decision {name!r} is already defined with other outcomes")
        self._name = name
        self._outcomes = allowed

    @property
    def name(self) -> str:
        return self._name

    @property
    def outcomes(self) -> frozenset[str]:
        return self._outcomes

    def record(self, outcome: O, *, reason: str | None = None) -> None:
        """Record this decision on the innermost active entry.

        Raises ``UnknownOutcomeError`` for an undeclared outcome, even outside
        an entry. A valid call outside an entry does nothing. The reason is kept
        in full.
        """

        value = _value(outcome)
        if value not in self._outcomes:
            raise UnknownOutcomeError(
                f"{value!r} is not an outcome of decision {self._name!r}; "
                f"expected one of {sorted(self._outcomes)}"
            )
        scope = current_scope()
        if scope is not None:
            scope.decisions.append(DecisionRecord(name=self._name, outcome=value, reason=reason))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Decision):
            return NotImplemented
        return (self._name, self._outcomes) == (other.name, other.outcomes)  # pyright: ignore[reportUnknownMemberType]

    def __hash__(self) -> int:
        return hash((self._name, self._outcomes))

    def __repr__(self) -> str:
        return f"Decision({self._name!r}, {sorted(self._outcomes)!r})"


def _value(outcome: object) -> str:
    if isinstance(outcome, Enum):
        return str(outcome.value)
    if not isinstance(outcome, str):
        raise TypeError(f"decision outcomes must be strings, got {outcome!r}")
    return outcome
