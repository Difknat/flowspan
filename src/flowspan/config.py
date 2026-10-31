"""Optional, process-wide settings. The defaults work without calling ``configure``."""

from __future__ import annotations

import dataclasses
import threading
from dataclasses import dataclass, field
from typing import Final, TypedDict, Unpack

from flowspan.evidence.classification import Classifier, TypeRegistry

MIN_ENTRY_BYTES: Final = 64


@dataclass(frozen=True, slots=True)
class Settings:
    """Flowspan's settings. Replace them with ``configure``, never by mutation.

    - ``classifier`` decides expected or unexpected before the type registry.
    - ``max_entry_bytes`` caps each exception entry on the span.
    - ``types`` holds the types registered with ``classify_as_expected`` and
      ``classify_as_unexpected``.
    """

    classifier: Classifier | None = None
    max_entry_bytes: int = 2048
    types: TypeRegistry = field(default_factory=TypeRegistry)

    def __post_init__(self) -> None:
        if self.max_entry_bytes < MIN_ENTRY_BYTES:
            raise ValueError(f"max_entry_bytes must be at least {MIN_ENTRY_BYTES}")


class SettingsChanges(TypedDict, total=False):
    classifier: Classifier | None
    max_entry_bytes: int
    types: TypeRegistry


_settings = Settings()
_lock = threading.Lock()


def current_settings() -> Settings:
    return _settings


def configure(**changes: Unpack[SettingsChanges]) -> Settings:
    """Replace the given settings and keep the rest. Returns the new settings."""

    global _settings
    with _lock:
        _settings = dataclasses.replace(_settings, **changes)
        return _settings
