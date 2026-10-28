# Task 0018: Complete structured tropical-provider data preservation

## Status

In progress

## Context

The library has nine registered tropical-system sources covering NHC/CPHC,
JMA, CMA/NMC, PAGASA, BoM, HKO, and Météo-France La Réunion. A review of
their implementations and current official products on 2026-10-28 found that
some providers publish useful structured facts that the adapters do not yet
preserve.

The review also found several products whose public presentation contains a
cone, probability area, or wind area, while the machine-readable source
contains only points, radii, axes, prose, or rendered images. Those products
must not be reconstructed by this library. A provider-published probability or
radius is useful source data; it is not permission to calculate a polygon,
buffer a track, join circles, or invent a confidence surface.

India Meteorological Department documents particularly useful cyclone track,
wind-polygon, and cone endpoints, but they currently require an API key. This
open-source library will not require maintainers or users to register for a
credential in order to use a built-in tropical source. IMD's keyed API is
therefore not an implementation candidate under this task.

## Problem

The current capability table can make two different limitations look alike:

- a parser may omit explicitly labelled values that are already present in an
  official structured payload; or
- the provider may not supply reusable geometry at all, even though its public
  website displays a derived or rendered area.

Treating the second case as an invitation to generate geometry would blur the
source boundary and give callers data the provider did not actually publish.
Conversely, leaving useful radii, gusts, forecast classifications, or timed
positions unrepresented makes the adapters less informative than their source
payloads.

PAGASA and WMO SWIC also expose promising browser-facing structured requests,
but their active-event lifecycle and field contracts need evidence before a
backend is designed.

## Desired outcome

Preserve additional useful, explicitly labelled tropical-system information
from official structured sources without manufacturing statistics or
geometry. Make an evidence-backed go/no-go decision for the anonymous PAGASA
and WMO SWIC candidates, and record clear no-go decisions where a useful
product requires credentials, PDF/image parsing, geocoding, or geometric
construction.

Each provider slice must be independently reviewable and mergeable. A failed
or unavailable optional enrichment must never hide an otherwise valid current
system.

## Scope

### Slice 1: Source-fidelity boundary

- Document and test the distinction between provider-supplied geometry and
  provider-supplied scalar or point data.
- Pass through a provider's GeoJSON, KML, GML, or equivalent explicit geometry
  only when its semantics are known.
- Preserve useful published radii, axes, thresholds, probabilities, and units
  as source facts in `parameters` or a structured lazy product.
- Do not turn those facts into polygons, buffers, envelopes, corridors, cones,
  or probability surfaces.
- Keep track, probability, wind, watch/warning, and forecast-area concepts
  semantically separate.

### Slice 2: JMA structured forecast facts

- Use JMA's existing public XML update feed and selected current VPTW report;
  do not add a second scraped presentation source.
- Extend the structured forecast product to retain useful explicitly labelled
  values currently omitted, where present, including forecast classification,
  maximum gust, probability-circle radius and unit, and storm-warning-area
  radius and unit.
- Preserve current strong-wind and storm-wind area axes/radii, thresholds, and
  units when their XML meaning is unambiguous.
- Retain the existing current centre and forecast-centre line unchanged.
- Treat JMA's 70% probability-circle values as provider metadata only. Do not
  construct circles, a union, an envelope, or a `cone` geometry from them.
- Add fixtures covering symmetric and asymmetric radii, missing optional
  values, and more than one forecast lead time.

Official evidence:

- XML update feed: `https://www.data.jma.go.jp/developer/xml/feed/extra.xml`
- tropical product catalogue:
  `https://www.data.jma.go.jp/suishin/cgi-bin/catalogue/make_product_page.cgi?id=Taifu`
- public detail presentation:
  `https://www.data.jma.go.jp/multi/cyclone/cyclone_detail.html`

### Slice 3: CMA/NMC wind-radius preservation

- Recheck the positional JSONP contract against a current event and fixtures.
- Preserve the published wind thresholds, quadrant radii, units, and analysis
  time in a structured and inspectable form while retaining the raw source
  values.
- Continue to use BABJ positions for the CMA forecast rather than relabelling
  other agencies' forecasts as CMA data.
- Do not construct wind polygons from quadrant radii.
- Do not parse or vectorize NMC's rendered track-probability images. Unless an
  official structured polygon is later found, CMA remains a track source with
  wind-radius metadata and no cone geometry.

Official evidence:

- active list: `https://typhoon.nmc.cn/weatherservice/typhoon/jsons/list_default`
- detail pattern:
  `https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_<internal-id>`
- rendered probability product:
  `https://www.nmc.cn/publish/typhoon/probability.html`

### Slice 4: HKO potential-track-area no-go

- Retain HKO's official analysed and timed forecast positions as track
  geometry.
- Record that HKO documents a 70% Potential Track Area and publishes the
  forecast-hour radii used by its public map, but its track XML does not supply
  that area as geometry.
- Do not copy the radius table into code, buffer the forecast fixes, infer the
  map's joining rule, or expose a locally generated potential-track polygon.
- Reconsider this decision only if HKO publishes the area itself through an
  official structured geometry endpoint.
- Keep untimed smooth display-curve vertices out of timed forecast markers;
  the separate `forecast_curve` vocabulary question remains in task 0017.

Official evidence:

- GIS presentation and probability description:
  `https://www.weather.gov.hk/en/wxinfo/currwx/tc_gis.htm`
- open-data track catalogue:
  `https://data.gov.hk/en-data/dataset/hk-hko-rss-tc-track-info`

### Slice 5: PAGASA active-event validation

- During a suitable active Philippine event, capture the official public
  application's response to `POST /api/track_points/{typhoon_id}` across at
  least two updates and through its inactive or ended transition when
  practical.
- Establish identifiers, timestamps, analysed/forecast distinction,
  coordinates, intensity fields, units, and lifecycle signals before designing
  a parser.
- Expose track or area geometry only if the response supplies that geometry or
  explicit coordinates directly.
- Do not geocode relative-location prose, calculate a cone from points or
  radii, parse bulletin PDFs, or extract geometry from graphics.
- If the request is unstable, incomplete, or has no reliable inactive state,
  record a no-go decision and retain the existing bulletin adapter.

Official evidence:

- current bulletin:
  `https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin/1`
- severe-wind application:
  `https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-wind-impact-based-forecast`

This slice extends the live-event process in task 0013 rather than replacing
it.

### Slice 6: Open India and global-gap evaluation

- Record IMD's native cyclone API as a no-go while it requires an API key. Do
  not register for a key, add credential configuration, bundle a shared key, or
  scrape IMD's PDF and image products.
- Evaluate WMO SWIC's anonymous browser-facing tropical JSON as a possible
  explicitly attributed source for RSMC New Delhi and other uncovered centres.
- Verify its active index, per-system request pattern, quiet-state behaviour,
  ended-system removal, stable identifiers, attribution, update times, and
  separation of observations from different RSMCs/TCWCs across multiple
  events.
- Preserve each contributing centre's identity. Do not silently replace or
  merge direct JMA, CMA, HKO, PAGASA, BoM, NHC/CPHC, or Météo-France source
  observations.
- Treat SWIC as a track/facts candidate only unless its response directly
  supplies clearly identified geometry. Do not infer cones or wind areas.
- If the browser-facing contract proves stable enough, create a separate
  numbered implementation task with captured fixtures; otherwise record a
  no-go decision.

Official evidence:

- IMD API reference: `https://api.imd.gov.in/public/api_reference.html`
- SWIC active tropical index:
  `https://severeweather.wmo.int/json/tc_inforce.json`
- SWIC per-system pattern:
  `https://severeweather.wmo.int/json/tc_<system-id>.json`
- SWIC attribution and reuse notes:
  `https://severeweather.wmo.int/note.html`

### Slice 7: Existing-task coordination

- Keep NHC/CPHC wind-field work in task 0005. It may normalize an official GIS
  asset that already contains geometry; it must not generate wind polygons
  from scalar radii.
- Keep seasonal/live validation in task 0013 and record PAGASA evidence there
  when captured.
- Keep BMKG implementation in task 0014.
- Keep track/curve vocabulary and display semantics in task 0017.
- Keep Météo-France wind contours as raw source data until their actual
  structured geometry and threshold semantics are verified.

## Non-goals

- Do not calculate, interpolate, smooth, buffer, union, project, or otherwise
  construct tropical-system geometry from points, tracks, bearings, distances,
  radii, axes, probabilities, or prose.
- Do not calculate confidence statistics or reinterpret a provider's stated
  probability.
- Do not call probability circles, potential-track areas, storm-warning areas,
  wind areas, and NHC cones interchangeable.
- Do not parse PDFs, images, screenshots, map tiles, or chart pixels.
- Do not geocode forecast place descriptions into coordinates.
- Do not add a built-in provider that requires an API key, login, cookie, or
  maintainer-managed secret.
- Do not use JTWC or another non-designated centre as a silent substitute for
  an official RSMC, TCWC, or national provider.
- Do not change tropical grouping, proximity matching, ordinary warning
  routing, or the public model's existing field meanings.
- Do not add live-network tests.

## Relevant code

- `wevva_warnings/models.py`
- `wevva_warnings/query.py`
- `wevva_warnings/sources.py`
- `wevva_warnings/registry.py`
- `wevva_warnings/backends/jma_tropical.py`
- `wevva_warnings/backends/cma_tropical.py`
- `wevva_warnings/backends/pagasa_tropical.py`
- `wevva_warnings/backends/hko.py`
- `wevva_warnings/backends/nhc_gis.py`
- `wevva_warnings/backends/meteofrance_reunion_tropical.py`
- `tests/test_cma_tropical.py`
- `tests/test_pagasa_tropical.py`
- `tests/test_hko_reunion_tropical.py`
- `tests/test_provider_backends.py`
- `docs/tasks/0005-enrich-nhc-cphc-tropical-gis-layers.md`
- `docs/tasks/0013-validate-tropical-source-follow-ups.md`
- `docs/tasks/0014-add-bmkg-tcwc-jakarta-tropical-source.md`
- `docs/tasks/0017-finish-tropical-display-scope-and-geometry-semantics.md`

## Approach

1. Implement and review one provider slice at a time. Do not combine unrelated
   provider changes merely because they share this task.
2. Start each slice by recording the exact official endpoint, observed date,
   lifecycle signal, units, and candidate fields.
3. Reduce official payloads to small deterministic fixtures before changing a
   parser. Fixtures must retain enough structure to prove field meaning while
   avoiding unnecessary bulk.
4. Preserve native values and units. Normalize only fields whose meaning maps
   directly to the existing public contract; retain other useful facts in
   `parameters` or the provider's lazy structured product.
5. Accept geometry only when the source payload itself encodes geometry or an
   explicit ordered track. Decline enrichment when geometry would have to be
   constructed.
6. Make every optional request best-effort and isolate its failure from core
   system discovery.
7. Update the capability table, architecture notes, source notes, fixtures,
   and provider tests in the same slice when observable support changes.

## Acceptance criteria

- The source-fidelity rule is reflected consistently in code, tests, source
  notes, and the tropical capability table.
- JMA exposes the selected additional labelled forecast and area-radius facts
  with their native units, without adding generated probability, warning, or
  wind polygons.
- CMA retains inspectable thresholded quadrant-radius data without adding
  generated wind polygons or a cone.
- HKO remains a truthful track source and does not expose a locally constructed
  Potential Track Area.
- PAGASA has either a fixture-backed structured-source decision or a documented
  current no-go reason based on active-event evidence.
- IMD's keyed API is explicitly excluded, with no credential or registration
  path added to the library.
- WMO SWIC has a reproducible go/no-go decision covering attribution,
  lifecycle, identifiers, overlap, and reuse terms.
- No slice parses a PDF/image or constructs geometry from scalar/point inputs.
- Missing or malformed optional data never suppresses a valid tropical-system
  observation.
- Existing source IDs, public model fields, grouping, and routing behaviour
  remain compatible.

## Verification

- Add or update deterministic mocked fixtures for every implemented provider
  slice; no test may depend on live provider availability.
- Cover missing optional values, malformed enrichment payloads, units,
  symmetric/asymmetric native radii, and multiple forecast leads where
  relevant.
- Assert that scalar radii or probability values do not produce new geometry
  keys.
- Run focused provider tests after each slice.
- Run the supported full workflow after code changes:

  ```bash
  uv run python -m unittest discover -s tests -v
  uv build
  ```

- Documentation-only evidence updates do not require a build, but must record
  the observation date and official endpoint.

## Decisions and notes

- "Provider-supplied geometry" means the provider payload encodes the geometry
  itself, such as GeoJSON coordinates, KML, GML, or an equivalent official
  geometry object. A centre plus radius is not provider-supplied polygon
  geometry.
- An ordered sequence of explicit analysed or forecast coordinates may remain
  an observed or forecast track. This does not authorize buffering the line or
  calculating an uncertainty corridor.
- JMA's published 70% probability-circle radius is retained only as JMA's
  stated value. The library does not calculate the probability or its area.
- HKO's published radius table explains its public map but is not an input to
  library geometry.
- IMD's documented native endpoints are technically strong but unsuitable as
  a built-in source while authentication is mandatory.
- WMO SWIC is an official aggregator rather than the issuing centre. Any future
  source must make that distinction and retain the actual centre attribution.

## Outcome

Slice 1 completed on 2026-10-28. The public model documentation, README,
architecture, and tropical source notes now state the source-fidelity boundary:
explicit provider geometry and ordered track coordinates may be normalized,
while scalar radii, axes, distances, thresholds, probabilities, and prose do
not create area geometry. Regression assertions cover JMA probability radii,
CMA quadrant wind radii, PAGASA textual wind extent, HKO timed track fixes, and
Météo-France wind-contour metadata without generated layers.

The remaining provider slices are not started.
