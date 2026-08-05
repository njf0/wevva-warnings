# Task 0001: Add composable alert-access tools to `wevva-warnings`

## Status

Completed

## Target repository

`../wevva-warnings`

## Context

`wevva-warnings` currently offers a point query and a single-source query.
The point query deliberately combines country/language source selection,
provider retrieval, geometry resolution, and point matching in one operation.
That is ideal for a simple caller, but makes richer consumers repeat internal
logic or repeat country-wide provider work.

Examples include a TUI that moves from Berlin to Munich, a map that needs to
show several points in Germany, and a caller that wants to inspect all current
candidate warnings from the sources selected for a country.

## Problem

There is no supported public way to:

- discover the alert sources selected for a country/language request;
- retrieve reusable country-level alert candidates; or
- match an already-fetched candidate collection to one or more points.

Calling `get_alerts_for_point()` repeatedly is correct but repeats provider
work. Calling `get_alerts_for_source()` is too low-level: callers must know
source IDs and would otherwise have to reproduce country/language selection and
point-matching semantics.

## Desired outcome

Provide a small, composable public Python toolkit that exposes the existing
query stages without changing `get_alerts_for_point()` behaviour:

```python
from wevva_warnings import (
    get_alert_sources_for_country,
    get_alerts_for_country,
    match_alerts_to_point,
)

candidates = get_alerts_for_country("DE", lang="en")
berlin_alerts = match_alerts_to_point(candidates, lat=52.52, lon=13.405)
munich_alerts = match_alerts_to_point(candidates, lat=48.137, lon=11.575)
```

This gives applications a correct country-level cache boundary: they cache
`candidates` using their own policy, then call `match_alerts_to_point()` for
each location. The warning library remains synchronous and does not gain a
cache, scheduler, configuration store, or persistence layer.

## Scope

- Add and export `get_alert_sources_for_country(country_code, *, lang=None)`.
  It returns the alert `WarningSource` values selected with the same
  country/language rules as point queries, including the existing default
  English preference and unsupported-language fallback behaviour.
- Add and export
  `get_alerts_for_country(country_code, *, lang=None, active_only=False,
  progress=None) -> list[Alert]`.
  It retrieves alert candidates from the selected country sources without
  applying a point filter, attaches `source_info`, resolves available geometry,
  applies source-level ID deduplication, and honours `active_only`.
- Add and export
  `match_alerts_to_point(alerts, *, lat, lon, active_only=False) -> list[Alert]`.
  It resolves missing supported geometry when possible, excludes candidates
  without usable geometry, applies the existing point-query semantic
  deduplication, and honours `active_only`.
- Keep `get_alerts_for_point()` as the convenient, provider-optimised path.
  It must preserve its return values, language fallback, exceptions,
  `active_only` behaviour, and documented progress events. Refactor shared
  local matching only where that can be done without changing those semantics.
- Define the country-query progress contract in the architecture document.
  Use a distinct initial event (for example `country_query_started`) rather
  than changing the existing point-query event payload. Reuse the established
  source and candidate progress reporting where applicable.
- Add a useful CLI inspection command such as
  `wevva-warnings country COUNTRY_CODE [--lang LANG] [--active] [--formatted]`
  for listing country-level candidates. Do not add a CLI command that requires
  callers to serialize arbitrary `Alert` objects merely to invoke matching.
- Update `README.md`, `docs/architecture.md`, `wevva_warnings/__init__.py`,
  and the CLI help to document the new public surface.

## Non-goals

- Do not add caching, TTLs, background refreshes, persistence, or settings to
  `wevva-warnings`.
- Do not infer a country from coordinates.
- Do not require application callers to import `query.py`, `registry.py`,
  backends, or geometry internals.
- Do not remove, rename, or weaken existing point/source/tropical APIs.
- Do not build a generic provider framework or rewrite every backend's error
  handling as part of this task.
- Do not promise that a provider can supply a complete country-wide candidate
  collection when its upstream API only supports constrained point/bounding-box
  queries. Handle such a provider deliberately and document its behaviour.

## Relevant code

- `wevva_warnings/query.py`
- `wevva_warnings/registry.py`
- `wevva_warnings/geometry.py`
- `wevva_warnings/geocoding.py`
- `wevva_warnings/models.py`
- `wevva_warnings/__init__.py`
- `wevva_warnings/cli.py`
- `wevva_warnings/backends/base.py` and affected backends
- `tests/test_query.py` and geometry/provider fixtures
- `README.md` and `docs/architecture.md`

## Approach

Make the public tools thin compositions of the existing internals; do not
reimplement backends outside their current boundary.

1. Extract the country/language source-selection and fallback handling now
   embedded in the point query into a shared internal helper. Export the
   source-selection form as `get_alert_sources_for_country()`.
2. Implement `get_alerts_for_country()` by fetching each selected source
   without point coordinates, attaching source metadata, resolving supported
   geometry, applying `active_only`, and source-level deduplication. Preserve
   raw `geocodes`, `parameters`, and provider fields on every `Alert`.
3. Implement `match_alerts_to_point()` from the existing local geometry match,
   expiry/active handling, and semantic point-result deduplication. It must not
   make network calls.
4. Keep the current point query's native point-route and point-aware provider
   optimisations. It may share matching helpers for non-native candidates, but
   must not be silently changed into a country-wide fetch.
5. Add the CLI country inspection command as a thin caller of the public
   country API.

Native point-query providers deserve explicit treatment. Their existing point
query remains the preferred efficient path. The new country query may only
include a source when it can deliberately return a usable country candidate
collection with geometry; otherwise it must be documented as unsupported or
omitted with a clear progress/debug indication. Do not fake country candidates
from one point's response.

## Acceptance criteria

- A caller can obtain the same default/explicit-language source selection used
  by a point query without importing registry internals.
- A single country candidate fetch can be matched to Berlin and Munich without
  any network call during either matching operation.
- A warning whose geometry contains Munich but not Berlin is returned only for
  Munich from that same candidate collection.
- Changing country or language requires a separate candidate fetch; changing
  only point coordinates does not.
- Candidate and point-match paths preserve source metadata, raw geocodes, and
  parameters.
- `match_alerts_to_point()` excludes missing/unresolvable geometry, honours
  `active_only`, and retains the current point-query semantic deduplication.
- `get_alerts_for_point()` remains compatible, including current progress event
  names and payloads, native point routing, language fallback, and
  `UnsupportedCountryError` behaviour.
- `get_alerts_for_country()` has documented country-query progress behaviour
  and does not alter point-query progress behaviour.
- The new country CLI command uses only the public country API and renders
  candidates successfully with mocked fixtures.
- No live provider calls are required for the test suite.

## Verification

- Add standard-library `unittest` coverage with mocked backend responses for:
  country/language source selection; candidate retrieval; Berlin/Munich
  matching from one fetched list; missing geometry; `active_only`; semantic
  deduplication; language fallback; and source metadata preservation.
- Add a fixture-backed native-point-provider case that documents and verifies
  its country-query policy.
- Keep existing point-query and progress tests passing unchanged.
- Test the new CLI country command with mocked public API calls.
- Run `uv run python -m unittest discover -s tests -v`.

## Decisions and notes

- These tools intentionally make reusable data access possible without
  prescribing an application cache. A caller such as `wevva` owns TTL,
  cancellation, and session lifetime.
- `list_sources()` remains global registry inspection. The new country source
  helper answers a different question: which alert sources would this request
  actually use?
- A later task may add structured per-source completion/failure reporting if a
  cache consumer needs to distinguish a successful empty country response from
  a provider failure. Do not broaden every backend's error contract here unless
  that is required to make the new APIs truthful.

## Outcome

Implemented `get_alert_sources_for_country()`,
`get_alerts_for_country()`, and `match_alerts_to_point()` as public APIs,
plus the `wevva-warnings country` inspection command. Country candidate
queries share point-query source selection and language fallback, preserve
metadata, resolve packaged geometry, and support country-specific progress
events. NWS uses its national no-point feed for country candidates while its
native point query remains unchanged.
