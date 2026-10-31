# Using Flowspan

Follow this when adding Flowspan to a microservice, an early data pipeline, or a
scheduled job. Flowspan records what the code did. The application keeps the
meaning: its own exception types, its own decisions, and the OpenTelemetry SDK.

A worked example is [`examples/sales_report`](../examples/sales_report/build_report.py).

## Install

```bash
pip install flowspan 'opentelemetry-sdk>=1.27' 'opentelemetry-exporter-otlp-proto-http>=1.27'
```

Import the annotation from the package. Do not import `opentelemetry.sdk` inside
library code that only needs to record.

```python
from flowspan import (
    Decision,
    ExceptionKind,
    FunctionType,
    classify_as_expected,
    flowspan,
    record_exception,
)
```

## Mark functions

Put `@flowspan(FunctionType.X)` on the functions that make up one run. One
annotation is the whole API. Sync and async functions are both accepted.
Generator functions and async generators raise `TypeError`.

Place `@flowspan` below `@staticmethod` and `@classmethod`, so it wraps the raw
function:

```python
class Orders:
    @staticmethod
    @flowspan(FunctionType.ENTRY)
    def place(amount: int) -> str: ...
```

| `FunctionType` | Use it for | Span | Counted |
| -------------- | ---------- | ---- | ------- |
| `ENTRY` | The run a person would ask about: one request, one pipeline job, one schedule tick. Also a nested run that should have its own span. | yes, named after the function | no |
| `RULE` | A branch that chooses an outcome. | no | yes |
| `HELPER` | Local work: parse, validate shape, read a file, write a file, aggregate. | no | yes |
| `CLIENT` | A call that leaves the process: HTTP, database, queue, another service. | no | yes |

`RULE`, `HELPER`, and `CLIENT` record into the innermost `ENTRY`. Called outside
any `ENTRY`, they just run the function and record nothing.

An `ENTRY` called inside another `ENTRY` is a nested entry. It gets a child span
and keeps its own decisions and exceptions. Anything recorded before or after
that call belongs to the parent.

Do not mark every function. Mark the entry, the branches, the helpers that can
fail, and the outbound calls. Leave trivial getters unmarked.

Two `ENTRY` functions with the same `__name__` are recorded under the same name.
Give those functions different names.

## Record decisions

Define each decision once, at module level, with a closed set of outcomes. Prefer
a `StrEnum` so a wrong outcome is a type error. A set of strings is also valid.

```python
from enum import StrEnum
from flowspan import Decision, FunctionType, flowspan


class OrderGate(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


ORDER_GATE = Decision("order_gate", OrderGate)


@flowspan(FunctionType.RULE)
def gate(amount: int) -> bool:
    if amount < 10:
        ORDER_GATE.record(OrderGate.REJECTED, reason="amount_below_threshold")
        return False
    ORDER_GATE.record(OrderGate.ACCEPTED)
    return True
```

Rules:

- One `Decision` per question the code answers, not one per branch site.
- Call `record` at the branch, with a declared outcome. `reason` is optional and
  is kept in full.
- An outcome that was not declared raises `UnknownOutcomeError`, including when
  no entry is active.
- A declared outcome recorded outside an entry is ignored.
- The same name with the same outcomes may be defined again. The same name with
  different outcomes raises `ValueError`.
- Do not encode a decision by raising an exception.

## Classify exceptions

Flowspan ships no exception classes. Define them in the application, then say
which are expected outcomes. Everything else is unexpected.

```python
from flowspan import classify_as_expected, classify_as_unexpected

classify_as_expected(OutOfStock, NotFound)
classify_as_unexpected(GatewayTimeout)
```

Register types at startup, not inside the run. A subclass follows the nearest
registered base. Registering the same type again replaces the earlier kind.

When the type is not enough, pass a classifier to `configure`. It runs first.
`None`, or a classifier that raises, falls through to the registered types.

```python
from flowspan import ExceptionKind, configure

configure(
    classifier=lambda exc: ExceptionKind.EXPECTED if getattr(exc, "expected", False) else None
)
```

Recording:

- An exception that propagates out of a decorated function is recorded once,
  against the function it leaves.
- When the code catches an exception and does not re-raise it, call
  `record_exception(exc)` in the `except` block. That is the only manual call.
- Do not call `record_exception` for an exception you are about to re-raise out
  of a decorated function. Propagation records it.
- `record_exception` outside an entry does nothing.
- Only unexpected exceptions set the span status to `ERROR` and add an
  OpenTelemetry `exception` event.
- `KeyboardInterrupt`, `SystemExit`, and cancellation are never recorded.

## Install the SDK in the application

Flowspan imports only `opentelemetry-api`. Until the application installs an SDK,
it records nothing. Set `service.name` on the OpenTelemetry Resource.

```python
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider(resource=Resource.create({"service.name": "orders"}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
```

Do this once at process start, before the entry runs. Do not hide it inside a
decorated helper.

## What one span shows

On each entry span:

| Attribute | Meaning |
| --------- | ------- |
| `flowspan.entry.name` | The `ENTRY` function's `__name__` |
| `code.function.name` | The function's `__qualname__` |
| `flowspan.function.type` | `entry` |
| `flowspan.decisions` | `name: outcome` or `name: outcome: reason`, only when non-empty |
| `flowspan.exceptions` | `expected` or `unexpected`, then function, type, and message. Only when non-empty |

Each exception entry is capped at 2048 bytes unless `configure(max_entry_bytes=...)`
sets a larger cap. The minimum is 64.

`flowspan.function.calls` counts `RULE`, `HELPER`, and `CLIENT` calls inside an
entry. Attributes are `flowspan.entry.name` (the innermost entry),
`code.function.name`, `flowspan.function.type`, and `flowspan.outcome`
(`success`, `expected_exception`, or `unexpected_exception`). An exception that
passes through several functions is counted once.

## Context

`asyncio` tasks keep the entry they were started in. A thread pool does not.
Submit pool work with `contextvars.copy_context().run` so it stays inside the
current entry.

## Checklist

1. Find the function a person would name when asking what happened. Mark it `ENTRY`.
2. Mark nested runs that need their own span as `ENTRY`.
3. Mark outcome branches as `RULE`, local work as `HELPER`, and outbound calls as `CLIENT`.
4. Define one `Decision` per question, and `record` it at the branch.
5. Classify the application's exception types at startup.
6. Call `record_exception` only for an exception that is caught and not re-raised.
7. Install the OpenTelemetry SDK in the application and set `service.name`.
