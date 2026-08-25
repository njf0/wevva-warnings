# Task 0017: Finish tropical display scope and geometry semantics

## Status

Proposed

## Target repositories

`../wevva-warnings` and `../wevva`

## Context

The current tropical API now provides source observations, conservative
explicit-name groups, source-and-basin display-geography resolution, named
geometry layers, and lazy supplementary products. The implementation is
deliberately small and fixture-tested.

Two presentation questions remain intentionally unresolved. First, NHC Eastern
Pacific observations currently fall back to `country` `US`; a whole-country
Natural Earth shape includes Alaska and other components that produce a poor
map scope for storms near Mexico. Earlier experiments with a blanket Mexico
hint were also misleading, so the fallback was restored. Second, some
providers expose useful smooth or historical trajectories whose semantics do
not fit the existing normalized geometry keys.

## Problem

Without a bounded follow-up, downstream code may add source-ID conditionals,
coordinate heuristics, or treat all line geometry as forecast fixes. Those
shortcuts would undermine the declarative source boundary and repeat the HKO
marker bug fixed in the current work.

## Desired outcome

Agree and implement the smallest cross-repository contract needed for useful
map scope and truthful track rendering, while preserving current source data
and avoiding geographic or meteorological inference.

## Scope

- Test whether `DisplayGeography` needs one optional, generic Natural Earth
  component selector, such as a mainland/largest-component preference.
- If adopted, configure it declaratively for the precise NHC Eastern Pacific
  case and teach `wevva`'s generic geography resolver to honor it. Do not add
  NHC-specific client logic.
- Keep CPHC mapped to Hawaii and Météo-France La Réunion mapped to Réunion.
- Decide whether the normalized geometry vocabulary should add a distinct
  `forecast_curve` key. If so, HKO may preserve its untimed smooth curve there,
  while `forecast_track` and product points remain timed fixes only.
- Validate Météo-France trajectory point types before replacing its current
  mixed `track` layer with separate `observed_track` and `forecast_track`
  layers.
- Investigate NHC's retained preliminary-best-track URL only if a stable
  official asset can be parsed without turning archive/history data into
  current-state fields.
- Document which geometry keys produce lines, point markers, probability
  areas, cones, or official watch/warning containment in `wevva`.

## Non-goals

- Do not choose geography from storm coordinates, longitude thresholds,
  nearest-country calculations, or live track intersections.
- Do not add Mexico/Baja/Hawaii switching, multi-country map composition, or
  an exhaustive source-to-region table.
- Do not merge observed, forecast, smoothed, cone, wind, and warning geometry.
- Do not infer forecast valid times for untimed source vertices.
- Do not implement historical archives or canonical meteorology.

## Relevant code

- `wevva_warnings/sources.py`
- `wevva_warnings/models.py`
- `wevva_warnings/backends/hko.py`
- `wevva_warnings/backends/meteofrance_reunion_tropical.py`
- `wevva_warnings/backends/nhc_gis.py`
- `tests/test_tropical_grouping.py`
- `tests/test_hko_reunion_tropical.py`
- `tests/test_provider_backends.py`
- `../wevva` Natural Earth geography resolution and storm-track rendering
- `docs/tasks/0012-operationalise-tropical-systems-in-wevva.md`
- `docs/tasks/0013-validate-tropical-source-follow-ups.md`

## Approach

1. Reproduce the NHC Eastern Pacific map scope with the exact Natural Earth
   dataset and geometry resolution used by `wevva`.
2. Specify a provider-neutral component selector only if the dataset offers a
   stable, testable interpretation. Otherwise retain the honest US fallback
   and document the display limitation.
3. Add fixture tests at both boundaries: source/basin precedence in this
   repository and generic component resolution in `wevva`.
4. For every proposed geometry key, capture an official fixture that proves
   its temporal and semantic meaning before changing the public vocabulary.
5. Keep marker generation tied to structured timed positions, never every
   vertex of a display line.

## Acceptance criteria

- NHC Eastern Pacific map context is materially useful without being labelled
  as Mexico solely because of the basin.
- NHC Atlantic behavior and CPHC Hawaii behavior remain unchanged.
- No source-ID or coordinate heuristic is added to `wevva`.
- HKO forecast markers remain exactly its ordered timed/indexed fixes.
- Any newly exposed curve or historical geometry has a distinct documented
  key and deterministic fixture coverage.
- README, architecture documentation, source notes, and both repositories'
  tests agree with the final contract.

## Verification

- Run this repository's focused geography/provider tests and full supported
  workflow: `uv run python -m unittest discover -s tests -v` and `uv build`.
- Run `wevva`'s existing tests and application smoke check after downstream
  changes.
- Record any live official payload inspection in task 0013; do not add live
  network tests.

## Decisions and notes

- The current committed behavior is intentional: NHC Eastern Pacific resolves
  to ordinary issuer-country `US`, not Mexico.
- A display geography is visual context. It does not identify storm ownership,
  coverage, impact, or warning jurisdiction.
- HKO's untimed curve remains omitted until a separate semantic key is agreed.
  Losing optional presentation smoothing is preferable to presenting curve
  vertices as forecast fixes.

## Outcome

Not started. Created on 2026-08-25 as the handoff for the remaining map-scope
and track-semantics decisions after the canonical grouping, product, and HKO
forecast-fix work.
