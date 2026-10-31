# Contributing

Thanks for helping improve Flowspan.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pre-commit install
```

## Checks

Every pull request must pass the same checks as CI:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pyright
.venv/bin/pytest --cov
```

Coverage must stay at or above 95%.

## Guidelines

- The runtime dependency is `opentelemetry-api` only. Never import
  `opentelemetry.sdk` from `src/`; a test enforces this.
- Keep the public API in `flowspan/__init__.py` small. Anything not in `__all__`
  is internal and may change.
- Respect the package boundaries in `docs/design.md`: only `flowspan.telemetry`
  imports OpenTelemetry, and `flowspan.context` imports nothing else from Flowspan
  besides its records and enums.
- Flowspan provides mechanisms. Do not add client conventions such as exception
  classes, decision names, or framework integrations to the core package.
- Name every new span attribute or metric in `flowspan/telemetry/conventions.py`.
- Add a test for every behavior change and an entry to `CHANGELOG.md`.
- Describe design changes in `docs/design.md`.
