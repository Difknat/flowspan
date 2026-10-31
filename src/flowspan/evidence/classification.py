"""Deciding whether an exception is expected or unexpected.

Flowspan ships no exception classes. The client either registers its own types
in a ``TypeRegistry`` or configures a ``Classifier`` callable, or both.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol

from flowspan.types import ExceptionKind


class Classifier(Protocol):
    """Return the kind of ``exc``, or ``None`` to fall back to the type registry."""

    def __call__(self, exc: BaseException, /) -> ExceptionKind | None: ...


class TypeRegistry:
    """Maps exception types to a kind. A subclass inherits its nearest registered base.

    Writes take a lock and replace the mapping, so reads need no lock.
    """

    __slots__ = ("_kinds", "_lock")

    def __init__(self) -> None:
        self._kinds: Mapping[type[BaseException], ExceptionKind] = MappingProxyType({})
        self._lock = threading.Lock()

    def register(self, kind: ExceptionKind, *exc_types: type[BaseException]) -> None:
        for exc_type in exc_types:
            if not (isinstance(exc_type, type) and issubclass(exc_type, BaseException)):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError(f"expected an exception type, got {exc_type!r}")
        with self._lock:
            self._kinds = MappingProxyType({**self._kinds, **dict.fromkeys(exc_types, kind)})

    def lookup(self, exc_type: type[BaseException]) -> ExceptionKind | None:
        kinds = self._kinds
        for klass in exc_type.__mro__:
            kind = kinds.get(klass)
            if kind is not None:
                return kind
        return None


def classify(
    exc: BaseException, classifier: Classifier | None, registry: TypeRegistry
) -> ExceptionKind:
    """The classifier first, then the registry, otherwise unexpected.

    A classifier that raises is ignored, so classification never raises into
    client code.
    """

    if classifier is not None:
        try:
            kind = classifier(exc)
        except Exception:
            kind = None
        if kind is not None:
            return kind
    return registry.lookup(type(exc)) or ExceptionKind.UNEXPECTED
