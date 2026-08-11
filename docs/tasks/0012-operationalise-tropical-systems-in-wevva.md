# Task 0012: Operationalise nearby tropical systems in `wevva`

## Status

Proposed

## Target repository

`../wevva`

## Context

`wevva-warnings` now has nine official tropical-system sources: NHC/CPHC,
JMA, CMA/NMC, PAGASA, BoM, HKO, and Météo-France La Réunion. The public
`get_tropical_systems_near()` helper returns a system when its current centre
is within a caller-selected radius or the requested point is contained in a
provider-supplied polygonal layer.

Returned `TropicalSystem` values contain common current facts (`classification`,
`max_wind`, `min_pressure`, `movement`, `issued_at`, centre and basin), source
metadata, named geometries, and selected provider-specific fields in
`parameters`. Current high-value examples include HKO peak intensity/wind,
NHC watch/warning text, JMA report serial, and Météo-France forecast peak.

## Problem

`wevva` currently presents ordinary country-routed warnings but has no clear,
consistent user-facing treatment for nearby storm systems. A centre within a
radius, a forecast cone, and an official warning polygon have different
meanings and must not be collapsed into an unqualified local warning.

## Desired outcome

Add a small tropical-systems surface to `wevva` that provides useful storm
context alongside ordinary warnings, promotes official impact coverage above
simple proximity, and remains honest about the issuer and match meaning.

## Scope

- Query `get_tropical_systems_near(lat, lon, radius_km=160.9)` as a separate
  operation from country warning retrieval and reusable-country caching.
- Calculate and render an exact centre distance locally when a centre exists.
- Surface systems whose centres are within 100 miles as “nearby tropical
  systems”, rather than turning them into ordinary weather-warning objects.
- Use `system.source_info.issuer_country_code`, when it equals the selected
  location's country code, only as a display-order preference among systems
  already matched by proximity or impact geometry. Do not filter systems by
  that field.
- Promote a source-provided warning/watch/wind-area containment match over
  centre-only proximity when match evidence is available from task 0004.
- Render a compact card or alert containing source, basin, current class,
  wind, pressure, movement, issue time and distance, plus an issuer URL.
- Render provider-specific values only with clear labels. In particular,
  label HKO peak values as historical and Météo-France peak values as forecast.
- Merge likely duplicate reports from different issuers for one display
  cycle, using normalised storm name plus close current centre and issue-time
  values. Preserve the individual source links/metadata on the merged result.
- Handle a zero-result or source-fetch failure as ordinary “no systems found”
  UI state; do not imply global absence of tropical activity.

## Non-goals

- Do not move tropical results into `get_alerts_for_point()` or country cache
  entries.
- Do not claim that a forecast track/cone is an official local warning.
- Do not write a persistent storm cache or polling system in this task.
- Do not invent cross-provider identity when the name, time, and centre do not
  support a conservative merge.
- Do not change `wevva-warnings` public interfaces from the downstream repo.

## Relevant code

- `wevva` location/forecast query flow and alert rendering components
- `wevva-warnings.get_tropical_systems_near()`
- `wevva-warnings.TropicalSystem`
- `../wevva-warnings/docs/tasks/0004-explain-tropical-proximity-matches.md`
- `../wevva-warnings/docs/architecture.md`

## Approach

1. Add a small service/function at the existing selected-location boundary;
   use the same final forecast coordinates that `wevva` displays.
2. Keep tropical retrieval independent from country alert caching. Query it
   only for the selected location and calculate distance with a local
   haversine helper.
3. Sort same-location issuers first when `issuer_country_code` is available,
   while retaining all nearby regional systems.
4. Start with a centre-radius card, then consume task 0004's explicit match
   evidence to distinguish `warning_area`/`watch_area` from cones and other
   descriptive geometry.
5. Define a deterministic merge key and retain a compact list of contributing
   sources. If uncertain, show separate cards rather than hiding a source.
6. Add fixture/fake-system tests for centre-only, direct impact, issuer-order
   preference, historical
   peak labelling, forecast peak labelling, duplicate candidates, and an empty
   response.

## Acceptance criteria

- A location within 100 miles of a system centre displays a nearby-system
  result with exact distance and current source facts.
- A direct official warning/watch/wind-area match receives stronger wording
  than a centre-only result; a forecast cone does not receive warning wording.
- Historical and forecast provider-specific facts are never displayed as the
  current storm intensity.
- Tropical results are never stored in the country-level ordinary-warning
  cache.
- A likely HKO/JMA or other cross-provider duplicate does not create
  confusing duplicate primary cards.
- Existing ordinary warning and forecast displays remain unchanged when no
  tropical system matches.

## Verification

- Use deterministic fake `TropicalSystem` values and mocked library queries.
- Exercise the UI manually with HKO when a current system is available and
  with a fixture or recorded payload for a warning-area containment case.
- Run `wevva`'s existing tests and its normal application smoke check.

## Decisions and notes

- 100 miles (160.9 km) is an initial discovery threshold, not a scientifically
  universal tropical-impact distance. Provider impact polygons take precedence
  when available.
- Task 0004 is the preferred upstream interface for explaining why a result
  matched; until it exists, avoid claiming a geometry-specific reason that
  the public library does not expose.
- `issuer_country_code` identifies an operational issuing location, not the
  storm's country, coverage area, or a source-selection rule.

## Outcome

Not started.
