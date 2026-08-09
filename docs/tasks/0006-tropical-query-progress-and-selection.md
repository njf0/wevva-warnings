# Task 0006: Add consumer-ready progress and selection to tropical queries

## Status

Proposed

## Target repository

`../wevva-warnings`

## Context

The ordinary alert APIs have a documented, exception-safe progress callback.
The tropical APIs are synchronous too, but only offer `debug` logging. A
tropical query can fetch one feed per basin and then retrieve multiple linked
GIS assets, so a TUI has no public way to report that work or distinguish an
empty result from source-by-source progress.

`get_tropical_systems_near()` already accepts an optional list of source IDs,
but a consumer otherwise has to fetch all tropical sources. The original
tropical design note envisaged selective basin/region queries without routing
systems through a country code.

## Problem

`wevva` cannot provide the same responsive query state for tropical lookups as
for ordinary warnings, and the public tropical API has no explicit selection
surface beyond source IDs on one helper.

## Desired outcome

Add a small, documented tropical query callback contract and explicit
source/basin-oriented selection helpers without adding a scheduler, cache, or
country inference.

## Scope

- Add an optional exception-safe `progress` callback to
  `get_tropical_systems_for_source()`, `get_tropical_systems_near()`, and the
  detailed match helper from task 0004 when it exists.
- Define tropical-specific event names and payloads in the architecture
  document. They must be distinct from stable alert point/country events.
- Emit enough information for a TUI to show source selection, source start,
  discovered system count, geometry/asset work when known, per-source finish,
  and final result count. Do not require every backend to report unavailable
  work-item counts.
- Add and export a simple basin selection helper, for example
  `get_tropical_systems_for_basin(basin, *, source_ids=None, progress=None)`,
  if the implementation can do so by filtering returned `TropicalSystem.basin`
  values without inventing source metadata or pre-filtering endpoints.
- Normalise accepted basin names in one documented place and return an empty
  result for a valid but presently uncovered basin. Do not silently infer a
  basin from caller coordinates.
- Update CLI commands with opt-in progress/debug rendering only where they
  call the public API.

## Non-goals

- Do not add a generic `active_only` parameter. Tropical providers do not yet
  expose a shared authoritative expiry/lifecycle model, and recency is not the
  same as active status.
- Do not add caching, polling, background refresh, cancellation, threads, or
  persistence to this library.
- Do not alter existing alert progress event names or payloads.
- Do not make `get_alerts_for_point()` implicitly fetch tropical systems.
- Do not require every tropical backend to implement native point filtering.

## Relevant code

- `wevva_warnings/query.py`
- `wevva_warnings/backends/base.py` and tropical backends
- `wevva_warnings/models.py`
- `wevva_warnings/__init__.py`
- `wevva_warnings/cli.py`
- `tests/test_query.py` and `tests/test_cli.py`
- `README.md` and `docs/architecture.md`

## Approach

1. Reuse the existing safe callback invocation helper or typing convention
   where appropriate, but define a separate tropical event vocabulary.
2. Create one internal tropical-query loop responsible for source selection,
   lifecycle events, source metadata attachment, and source/ID deduplication.
   Keep provider parsing and asset downloads inside their current backends.
3. Have both simple and detailed proximity helpers share that loop so they
   report the same source progress and do not duplicate requests.
4. Implement basin filtering after provider normalization. Make its matching
   rule exact and documented rather than attempting a world-region taxonomy.
5. Preserve current debug behaviour and source-ID filtering. Callback
   exceptions must never interrupt retrieval.

## Acceptance criteria

- A tropical source query and a proximity query emit documented tropical start,
  source, and completion events in deterministic order.
- Callback exceptions are ignored and leave results unchanged.
- Events report only selected sources and accurately distinguish fetched-system
  counts from proximity-match counts.
- A basin helper returns only systems whose normalised `basin` matches the
  requested basin, with no country or coordinate inference.
- Existing tropical query signatures and return values remain compatible when
  `progress` is omitted.
- Alert point/country progress behaviour remains unchanged.

## Verification

- Add fake backend/source tests for event order, selected-source filtering,
  callback failure, empty source results, and final counts.
- Add basin-filter tests using systems from more than one basin and an
  uncovered-basin case.
- Add mocked CLI tests for any new rendering flag.
- Run `uv run python -m unittest discover -s tests -v`.

## Decisions and notes

- A future lifecycle/freshness task may add source-specific status when there
  is truthful provider data. It should not overload `active_only` prematurely.
- Basin filtering is a convenience over normalised results, not a promise that
  every global basin is currently covered.

## Outcome

Not started.
