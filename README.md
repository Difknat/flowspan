# Flowspan

Flowspan is a small framework for seeing what your code did. Use it in a
microservice, an early data pipeline, or a scheduled job. Mark the entry point
and the functions under it. Each entry point gets one OpenTelemetry span that
carries the decisions the code made and the exceptions it hit, so one span
shows what happened.

Flowspan provides the mechanisms; your application keeps the meaning. Your code
defines its own exceptions and decisions. The service, pipeline, or job also
installs the OpenTelemetry SDK and an exporter. Until that SDK is installed,
Flowspan records nothing and costs almost nothing.

## Install

```bash
pip install flowspan 'opentelemetry-sdk>=1.27' 'opentelemetry-exporter-otlp-proto-http>=1.27'
```

Those two OpenTelemetry packages are what [`examples/sales_report`](examples/sales_report/requirements.txt) installs to export traces and metrics. Flowspan itself imports only `opentelemetry-api`.

## One annotation

```python
from flowspan import FunctionType, flowspan


@flowspan(FunctionType.ENTRY)
def place_order(amount: int) -> str:
    if not gate(amount):
        return "rejected"
    return charge(amount)


@flowspan(FunctionType.RULE)
def gate(amount: int) -> bool: ...


@flowspan(FunctionType.CLIENT)
def charge(amount: int) -> str: ...
```

| `FunctionType` | Span | Records into       | Counted |
| -------------- | ---- | ------------------ | ------- |
| `ENTRY`        | yes  | its own span       | no      |
| `RULE`         | no   | the innermost span | yes     |
| `HELPER`       | no   | the innermost span | yes     |
| `CLIENT`       | no   | the innermost span | yes     |

An `ENTRY` function is an entry point, named after the function. An `ENTRY`
function called inside another one is a nested entry point. It gets a child
span and keeps its own decisions and exceptions. Anything recorded before or
after it belongs to the parent. Outside any entry point, the other types just
call the function.

## Decisions

Define each decision once with its outcomes, then record it at the branch:

```python
from enum import StrEnum
from flowspan import Decision


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

A `Decision` built from a `StrEnum` only accepts that enum's members, so your
type checker catches a wrong outcome. You can also pass a set of strings. An
undeclared outcome raises `UnknownOutcomeError`.

## Exceptions

Flowspan ships no exception classes. Tell it which of your types are expected
outcomes; everything else is unexpected:

```python
import flowspan
from myapp.errors import OutOfStock, NotFound

flowspan.classify_as_expected(OutOfStock, NotFound)
```

When types are not enough, configure a classifier. It runs first; returning
`None` falls back to the registered types:

```python
from flowspan import ExceptionKind, configure

configure(
    classifier=lambda exc: ExceptionKind.EXPECTED if getattr(exc, "expected", False) else None
)
```

Exceptions that propagate out of a decorated function are recorded
automatically, once, against the function that raised them. For an exception
your code catches and handles, call `record_exception(exc)`.

Only unexpected exceptions set the span status to `ERROR` and add an `exception`
event. Cancellation, `KeyboardInterrupt`, and `SystemExit` are never recorded.

## What is emitted

Span attributes on each entry point:

| Attribute              | Example                                                        |
| ---------------------- | -------------------------------------------------------------- |
| `flowspan.entry.name`     | `place_order`                                                  |
| `code.function.name`   | `OrderService.place_order`                                     |
| `flowspan.function.type` | `entry`                                                        |
| `flowspan.decisions`     | `["order_gate: rejected: amount_below_threshold"]`             |
| `flowspan.exceptions`    | `["unexpected: charge: myapp.errors.GatewayError: timeout"]`    |

The two lists are only set when non-empty. Each exception entry is capped at
2048 bytes by default.

One counter, `flowspan.function.calls`, counts rule, helper, and client
functions with the attributes `flowspan.entry.name` (the span the call ran in),
`code.function.name`, `flowspan.function.type`, and `flowspan.outcome` (`success`,
`expected_exception`, or `unexpected_exception`). An exception that passes through
several functions is counted once. The service comes from your OpenTelemetry
Resource (`service.name`).

## Configure the OpenTelemetry SDK

That is your application's job:

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

[`examples/sales_report`](examples/sales_report/README.md) is a complete program.
It reads a sales Parquet file, writes an insights Parquet file, and exports
traces and metrics to a local OpenObserve.

## Settings

`configure(...)` is optional and replaces only the settings you pass:

| Setting           | Default          | Meaning                                       |
| ----------------- | ---------------- | --------------------------------------------- |
| `classifier`      | `None`           | Decides expected or unexpected before the types |
| `max_entry_bytes` | `2048`           | Cap for each exception entry                  |
| `types`           | empty registry   | Types registered with `classify_as_*`         |

## Things to know

- Put `@flowspan` below `@staticmethod` and `@classmethod`.
- Generator functions are rejected with `TypeError`.
- Thread pools do not inherit context. Submit work with
  `contextvars.copy_context().run` to keep it inside the current entry point.
- Two `ENTRY` functions with the same `__name__` are recorded under the same name.

How to add Flowspan to a service, pipeline, or job is in [`docs/usage.md`](docs/usage.md).
The design is described in [`docs/design.md`](docs/design.md).

## License

[Apache-2.0](LICENSE). Copyright 2026 Difknat. See [NOTICE](NOTICE).
