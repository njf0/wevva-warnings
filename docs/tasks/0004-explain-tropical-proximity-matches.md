# Task 0004: Expose why a tropical system matched a location

## Status

Proposed

## Target repository

`../wevva-warnings`

## Context

`get_tropical_systems_near()` currently returns a `TropicalSystem` when either
its centre is within a caller-supplied radius or the point lies inside any
polygonal geometry layer. The model intentionally preserves named layers such
as `forecast_track`, `cone`, and `watch_warning`.

These geometries have materially different meanings. A forecast cone is
context about possible centre positions; an official watch/warning polygon is
an impact product. Returning only a bare system means a consumer cannot state
why it was surfaced or choose a suitable visual treatment.

## Problem

The existing helper is useful as a simple discovery API, but it conflates
centre proximity, forecast context, and official warning coverage. A TUI
cannot distinguish a nearby storm from an authoritative local tropical watch
or warning without reimplementing private matching logic.

## Desired outcome

Keep `get_tropical_systems_near()` fully compatible and add one small,
explicit public detail API for consumers that need match evidence.

The preferred shape is a public `TropicalSystemMatch` dataclass and
`get_tropical_system_matches_near(...) -> list[TropicalSystemMatch]`. Each
match should expose:

- the `TropicalSystem`;
- centre distance in kilometres when a centre is available;
- whether the requested radius matched the centre; and
- the names of all polygonal geometry layers that contain the point.

## Scope

- Add and export `TropicalSystemMatch` from `wevva_warnings`.
- Add and export `get_tropical_system_matches_near()` with the same coordinate,
  radius, source selection, error, and debug behaviour as the current simple
  helper.
- Refactor the existing point-match predicate so both APIs use one internal
  spatial evaluation and cannot drift.
- Preserve all containing layer names. Do not reduce them to an undocumented
  severity label or silently choose one layer.
- Document that a cone, track, wind field, and official watch/warning are
  different products whose interpretation belongs to the consumer.
- Add concise CLI support only if it can display match evidence without
  changing the existing `tropical-near` output. For example, an opt-in
  `--explain` flag may call only the new public API.
- Update API and architecture documentation.

## Non-goals

- Do not change the return type or matching behaviour of
  `get_tropical_systems_near()`.
- Do not call a forecast cone an alert, warning, impact probability, or
  landfall prediction.
- Do not calculate distance to a track, cone edge, coastline, or wind field in
  this task.
- Do not synthesize geometry where a provider did not publish it.
- Do not introduce a query-plan framework or global cross-source storm merge.

## Relevant code

- `wevva_warnings/models.py`
- `wevva_warnings/query.py`
- `wevva_warnings/__init__.py`
- `wevva_warnings/geometry.py`
- `wevva_warnings/cli.py`
- `tests/test_query.py` and `tests/test_cli.py`
- `README.md` and `docs/architecture.md`

## Approach

1. Add a compact immutable-or-slotted public model whose fields are sufficient
   to explain matching without duplicating the system payload.
2. Have a single internal evaluator compute the centre distance, radius match,
   and containing polygonal layer names. It should ignore non-polygon layers
   for containment while preserving their names on `TropicalSystem`.
3. Implement the new detail helper using the current tropical source routing,
   source metadata attachment, and source/ID deduplication rules.
4. Reimplement the existing simple helper as a projection from detailed
   matches, or have both consume the evaluator, while preserving ordering and
   results exactly.
5. Describe the matching contract prominently: a system is returned when one
   or more evidence fields match, and no evidence field alone implies a local
   official warning.

## Acceptance criteria

- Existing callers receive the same `list[TropicalSystem]` from
  `get_tropical_systems_near()` for equivalent backend responses.
- The detail API reports a centre-only match, a geometry-only match, and a
  combined match correctly.
- A point inside both a cone and a watch/warning geometry retains both layer
  names.
- A point inside a non-warning geometry is not presented by the library as an
  official warning.
- Source filtering, negative-radius validation, source metadata, and
  source/ID deduplication behave consistently with the existing helper.
- New public names are exported and documented.

## Verification

- Add fake-system tests for centre-only, cone-only, watch/warning-only,
  multiple-containing-layers, no match, and duplicate source/ID cases.
- Add compatibility tests proving the old helper's values and order are
  unchanged.
- Add a mocked CLI test if `--explain` is added.
- Run `uv run python -m unittest discover -s tests -v`.

## Decisions and notes

- Geometry layer names are provider metadata. The library should expose them
  faithfully; `wevva` can map known layer names to UI wording.
- This task creates explainability, not a universal tropical warning model.

## Outcome

Not started.
