# Task 0012: Operationalise nearby tropical systems in `wevva`

## Status

Implemented downstream; live visual verification and the normal release
transition remain tracked in `wevva/docs/tasks/0014-tropical-systems-screen-handoff.md`.

## Target repository

`../wevva`

## Context

`wevva-warnings` now has nine official tropical-system sources: NHC/CPHC,
JMA, CMA/NMC, PAGASA, BoM, HKO, and Météo-France La Réunion. The public
`get_tropical_systems_near()` helper returns a system when its current centre
is within a caller-selected radius or the requested point is contained in a
provider-supplied polygonal layer.

The library now also provides conservative cross-source name groups,
declarative display-geography resolution, and lazy provider-specific products.
These remove the need for `wevva` to infer storm identity, map context, wallet
URLs, or provider product codes.

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
- For a reusable per-source cache, call `get_tropical_systems()`, then
  `match_tropical_systems_to_point()` and `group_tropical_systems()` locally.
  Use the returned `CanonicalTropicalSystem` groups directly; do not recreate
  cross-source identity rules in `wevva`.
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
- Resolve map context from each observation's `display_geography`. An explicit
  hint has already been resolved by source and basin; otherwise it is the
  issuer-country fallback. Do not derive display geography from coordinates.
- Fetch `get_tropical_products(observation)` only when a user opens a selected
  source observation. Render each provider label and the declared `markdown`
  or `plain` content format; structured `data` remains provider-specific.
- Render provider-specific values only with clear labels. In particular,
  label HKO peak values as historical and Météo-France peak values as forecast.
- Present observations in one library-provided canonical group when their
  explicit names match. Preserve every observation and its source-specific
  meteorology; do not select or calculate group-level current conditions.
- Handle a zero-result or source-fetch failure as ordinary “no systems found”
  UI state; do not imply global absence of tropical activity.

## Non-goals

- Do not move tropical results into `get_alerts_for_point()` or country cache
  entries.
- Do not claim that a forecast track/cone is an official local warning.
- Do not write a persistent storm cache or polling system in this task.
- Do not extend the library's name-only identity rule with proximity, time,
  basin, cyclone-number, track, or fuzzy-name matching.
- Do not fetch supplementary products during background storm discovery.
- Do not change `wevva-warnings` public interfaces from the downstream repo.

## Relevant code

- `wevva` location/forecast query flow and alert rendering components
- `wevva-warnings.get_tropical_systems_near()`
- `wevva-warnings.group_tropical_systems()`
- `wevva-warnings.get_tropical_products()`
- `wevva-warnings.TropicalSystem`
- `wevva-warnings.CanonicalTropicalSystem`
- `wevva-warnings.TropicalProduct`
- `../wevva-warnings/docs/tasks/0004-explain-tropical-proximity-matches.md`
- `../wevva-warnings/docs/architecture.md`

## Approach

1. Add a small service/function at the existing selected-location boundary;
   use the same final forecast coordinates that `wevva` displays.
2. Keep tropical retrieval independent from country alert caching. Query it
   only for the selected location and calculate distance with a local
   haversine helper.
3. Group locally matched results with `group_tropical_systems()`. Keep its
   deterministic group and observation order unless the UI applies a clearly
   documented presentation sort.
4. Start with a centre-radius card, then consume task 0004's explicit match
   evidence to distinguish `warning_area`/`watch_area` from cones and other
   descriptive geometry.
5. Pass each observation's resolved `display_geography` to the presentation
   layer without adding source checks or coordinate heuristics downstream.
6. Retrieve products only after observation selection and preserve declared
   labels, formats, ordering, links, issue times, content, and structured data.
7. Add fixture/fake-system tests for centre-only, direct impact, canonical
   groups, resolved geography, product formats, historical peak labelling,
   forecast peak labelling, and an empty response.

## Acceptance criteria

- A location within 100 miles of a system centre displays a nearby-system
  result with exact distance and current source facts.
- A direct official warning/watch/wind-area match receives stronger wording
  than a centre-only result; a forecast cone does not receive warning wording.
- Historical and forecast provider-specific facts are never displayed as the
  current storm intensity.
- Tropical results are never stored in the country-level ordinary-warning
  cache.
- A library-provided canonical group produces one primary storm surface while
  retaining all of its source observations.
- Opening details is the only action that triggers lazy product requests; one
  failed or empty product set does not remove the storm summary.
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
- `display_geography` is visual context, not storm ownership or an affected
  area. CPHC currently resolves to Hawaii and La Réunion to Réunion; ordinary
  sources resolve to their issuer country.
- Canonical groups express explicit-name identity only. Their observations are
  not candidates for meteorological averaging or reconciliation.

## Outcome

Implemented in the sibling `wevva` checkout with deliberate product-design
changes from this original nearby-card proposal. The main screen retains a
compact nearby launcher and location-specific alert tabs, while rich global
investigation moved to a dedicated Tropical Systems screen. Global canonical
discovery is cached independently from location matching; the current local
matching radius is 250 km. Storm tabs are severity-ordered and retain every
source observation without merged meteorology.

The final storm map uses a track-and-cone-fitted global Natural Earth backdrop.
Resolved `display_geography` supplies a label only when its geometry is visible;
it no longer selects or constrains the land layer. Lazy products, structured
source summaries, centre weather, responsive layout, and track/cone toggles are
covered by the downstream tests and architecture documentation. The editable
local dependency remains intentional until a compatible release is published.
Optional display-component and smooth-curve vocabulary work remains separately
proposed in task 0017 and is not required by the implemented downstream screen.
