# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - unreleased

### Added

- `@flowspan(FunctionType.X)` with `ENTRY`, `RULE`, `HELPER`, and `CLIENT`.
- One span per entry, with nested entries that keep their own evidence.
- `record_exception` for handled exceptions; propagating exceptions are recorded automatically.
- `classify_as_expected`, `classify_as_unexpected`, and an optional classifier callable.
- `Decision`, a typed handle for business decisions.
- `configure` and `Settings` for the classifier, the entry size cap, and the type registry.
- `flowspan.*` span attributes and the `flowspan.function.calls` counter.
