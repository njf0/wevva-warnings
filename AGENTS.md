# AGENTS.md

## Purpose

`wevva-warnings` is a small Python library and CLI for retrieving official
weather warnings for a point. Callers supply latitude, longitude, and an ISO
3166-1 alpha-2 country code; the library routes to registered sources,
normalizes their data, and matches returned warning areas to the point.

It also exposes separate tropical-system source and proximity queries.

## Map

- `wevva_warnings/__init__.py` is the public Python API.
- `query.py` orchestrates source selection, fetching, point matching, active
  filtering, and deduplication.
- `models.py` defines public `Alert` and `TropicalSystem` dataclasses.
- `sources.py` is the canonical built-in source registry; `registry.py` maps
  source backend names to implementations.
- `backends/` contains provider adapters. `base.py`, `_cap_feed.py`, and
  `generic_cap.py` are shared backend utilities.
- `cap.py`, `geometry.py`, and `geocoding.py` handle CAP normalization and
  geometry resolution/matching.
- `tests/` uses the standard library `unittest` framework and mocked payloads.

Read `docs/architecture.md` before changing routing, models, geometry, or a
provider. Read `docs/development.md` before running tooling.

## Commands

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv build
```

There is no configured formatter, linter, type checker, CI workflow, or
automated release command. Do not imply that one exists.

## Change principles

- Preserve the public names exported by `wevva_warnings.__init__`, model field
  meanings, CLI command behaviour, and source IDs unless a task explicitly
  authorizes a documented breaking change.
- Treat `get_alerts_for_point(..., progress=...)` event names and documented
  payload keys as a stable public API. Emit progress through the shared helper;
  never let a callback exception affect warning retrieval.
- Keep provider-specific facts in a backend or `WarningSource.notes`; do not
  discard useful raw geocodes or parameters just to make fields uniform.
- Prefer a small explicit backend. Reuse the existing CAP helpers when the
  input genuinely fits them; do not create a provider framework.
- Point-query routing depends on geometry. A non-native backend must produce a
  `Polygon`/`MultiPolygon` or a supported geocode that can resolve to one.
- Add deterministic fixture-based tests for changed parsing, routing, language,
  geometry, and deduplication behaviour. Avoid live-network tests.
- Keep source definition, backend registration/import, tests, README (when the
  user-facing API or support changes), and architecture documentation in sync.

## Adding a provider

1. Verify that the upstream endpoint is official, record its stable URL and
   language/country metadata in `sources.py`, and decide whether it is an
   `alert` or `tropical_system` source.
2. Reuse `generic_cap` only for genuinely generic CAP feeds; otherwise add a
   focused backend implementing `WarningBackend`.
3. Register the backend in `backends/__init__.py` and `registry.BACKENDS`.
4. Preserve source IDs, provider metadata, raw `geocodes`, and `parameters`.
   Supply usable geometry for non-native point queries.
5. Add mocked tests and update the relevant concise documentation.

Use `docs/tasks/0000-task-template.md` for new numbered work items.
