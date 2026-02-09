# INCIDENTS

Reliability incident log with root-cause analysis and prevention rules.

## Open incidents

- None.

## Prevention rules

- Changes to scan output schema must include CLI + scanner + summary test coverage to avoid silent contract drift.
- New network-facing features must support explicit timeouts and local deterministic unit tests using mocked I/O.
- Every autonomous maintenance run must capture exact validation commands and outcomes in `CLONE_FEATURES.md` and `PROJECT_MEMORY.md`.
