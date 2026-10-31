"""Pure functions that turn records into span attribute strings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from flowspan.context.records import DecisionRecord, ExceptionRecord

TRUNCATED: Final = "...[truncated]"


def exception_entry(record: ExceptionRecord, limit: int) -> str:
    """``<kind>: <function>: <exception type>: <message>``, capped at ``limit`` bytes."""

    return cap(f"{record.kind}: {record.function_name}: {record.exc_type}: {record.message}", limit)


def decision_entry(record: DecisionRecord) -> str:
    """``<name>: <outcome>`` or ``<name>: <outcome>: <reason>``. Never truncated."""

    if record.reason is None:
        return f"{record.name}: {record.outcome}"
    return f"{record.name}: {record.outcome}: {record.reason}"


def qualified_type_name(exc: BaseException) -> str:
    """The exception's fully qualified class name, without the ``builtins.`` prefix."""

    exc_type = type(exc)
    if exc_type.__module__ == "builtins":
        return exc_type.__qualname__
    return f"{exc_type.__module__}.{exc_type.__qualname__}"


def cap(text: str, limit: int) -> str:
    """Cut ``text`` to ``limit`` UTF-8 bytes, ending with ``TRUNCATED`` when cut."""

    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    keep = limit - len(TRUNCATED.encode("utf-8"))
    return encoded[:keep].decode("utf-8", errors="ignore") + TRUNCATED
