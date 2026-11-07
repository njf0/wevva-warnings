# Task 0018: Complete structured tropical-provider data preservation

## Status

Complete — Slices 1–6 have explicit outcomes and the stabilized provider
contracts are included in the `v0.6.0` release for the Wevva handoff

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

## Completion and consumer handoff

This task is upstream of Wevva Task 0035 and of the next `wevva-warnings`
release consumed by that application. JMA is the first completed rich
structured-product slice, not the final schema around which Wevva should design
its reader.

The task is complete only when:

- every Slice 1–6 investigation has a recorded outcome: implemented with
  fixtures, rejected with evidence, or explicitly left open because the
  required live lifecycle evidence does not yet exist;
- every implemented enrichment has stable documented public fields,
  optionality, source conditions, and native-unit behavior;
- capability/source documentation distinguishes provider data from generated
  geometry and accurately records each implementation or no-go decision;
- the complete suite and package build pass from a clean committed tree; and
- the release commit and version intended for Wevva are recorded.

An explicit no-go is a successful outcome when credentials, attribution,
lifecycle, reuse terms, payload stability, or the source-fidelity boundary make
an implementation unsuitable. A quiet endpoint is not by itself evidence for
either support or rejection: when a slice genuinely needs an active-event
lifecycle observation and none is available, keep that limitation visible
rather than inventing certainty.

The handoff order is strict:

1. finish these provider investigations and stabilize their public data shapes;
2. include the separately implemented NHC GIS/fix work required by Wevva in the
   same clean tested release boundary;
3. version and publish `wevva-warnings` with explicit maintainer approval;
4. remove Wevva's editable sibling override and lock that released version; and
5. only then redesign Wevva's shared structured-product presentation against
   the complete released fixture matrix.

Consumer formatting preferences must not drive provider parsing or force
unrelated centre-specific facts into a false common model. Conversely, if the
consumer review exposes missing source semantics, correct and release the
library contract rather than adding a provider parser or schema workaround in
Wevva.

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
- official map radius implementation:
  `https://typhoon.nmc.cn/js/typhoon/leaflet-typhoon.min.js`
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
- current CSDI spatial package:
  `https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/tc.zip`
- CSDI spatial archive:
  `https://data.weather.gov.hk/weatherAPI/hko_data/csdi/archive/tc.zip`

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
- structured request pattern retained in the site's application JavaScript:
  `POST https://www.pagasa.dost.gov.ph/api/track_points/<typhoon-id>`

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

- Every Slice 1–6 investigation has an explicit outcome; no provider candidate
  remains merely unreviewed at release handoff.
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
- The final implemented `TropicalSystem` and `TropicalProduct` shapes are
  documented and fixture-backed well enough for Wevva to present them without
  importing provider parsing knowledge.
- The task's release commit passes the complete suite and build before Wevva
  removes its editable dependency override.

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
- Wevva presentation work begins after this task's public shapes are stable and
  released. JMA remains a rich acceptance fixture, not a compulsory universal
  provider schema.

## Outcome

Slice 1 completed on 2026-10-28. The public model documentation, README,
architecture, and tropical source notes now state the source-fidelity boundary:
explicit provider geometry and ordered track coordinates may be normalized,
while scalar radii, axes, distances, thresholds, probabilities, and prose do
not create area geometry. Regression assertions cover JMA probability radii,
CMA quadrant wind radii, PAGASA textual wind extent, HKO timed track fixes, and
Météo-France wind-contour metadata without generated layers.

Slice 2 completed on 2026-10-28 using JMA's anonymous VPTW XML. The lazy
Forecast product now uses concise displayable classification, location,
movement, pressure, maximum-wind, and gust fields. Structured classification
components, alternate official units, and meaningful source conditions remain
available without repeating general XML attributes. Its additive current
analysis retains the analysis validity time, which can differ from report issue
time; current-only reports expose an Analysis product only when useful facts
exist beyond the ordinary `TropicalSystem`. Explicit but unparsed forecast
labels remain available without a derived lead. Probability-circle and wind or
storm-warning thresholds, axes, and radii remain provider facts only: the
existing `forecast_track` is unchanged and no area geometry is created.
Fixtures cover paired units, symmetric and asymmetric axes, multiple explicit
leads, an unparsed label, categorical movement, malformed optional radii, and
current-only reports.

This JMA result is a restraint checklist for later CMA, HKO, and other provider
slices, not a compulsory cross-provider data abstraction.

Slice 3 completed and received an active-event follow-up on 2026-11-07 using
CMA/NMC's anonymous list, detail, and official map-client resources. Tropical
Storm CEMPAKA appeared in the list with the active `start` lifecycle and linked
to a matching active detail record. Its current analysis was 19.7°N, 143.2°E,
20 m/s, 995 hPa, moving WNW at 27 km/h. The published `30KTS` radii were 200 km
northeast, 150 km southeast, 150 km southwest, and 250 km northwest. BABJ
supplied explicit forecast fixes at 12, 24, 36, 48, 60, 72, 96, and 120 hours.
The official map client independently confirms that wind-radius positions 1–4
mean northeast, southeast, southwest, and northwest and that their values are
kilometres.

The lazy CMA product now exposes the current analysis validity time and each
recognized provider threshold with its available quadrant radii. The original
compact positional array remains unchanged in `CMA Wind Radii` parameters.
BABJ forecast fields and geometry are unchanged; an analysis with useful radii
can remain available when BABJ forecast fixes are absent. Missing thresholds,
malformed individual radii, and missing forecast leads remain graceful, and no
wind polygon or other area geometry is constructed. This provider-specific
shape follows the JMA restraint checklist without adopting JMA's detail schema.
The reduced active-event fixture proves the list/detail relationship,
asymmetric current radii, and multiple explicit BABJ leads without introducing
CEMPAKA-specific production parsing or identifiers.
For the later Wevva handoff, CMA's existing point fields and explicit leads are
unchanged, so current track and forecast-row behavior remains compatible. The
new `analysis.wind_radii` detail is optional presentation material for the
shared product renderer; no CMA rendering policy belongs in this library.

Slice 4 completed on 2026-11-07 as an evidence-backed HKO Potential Track Area
no-go. HKO's GIS page describes the displayed area as the probable area within
which the cyclone centre will fall with 70% probability and publishes a table
of radii for the analysed position and the 24-, 48-, 72-, 96-, and 120-hour
forecast positions. Those radii are updated from historical forecast-error
statistics; they are not values carried by each tropical-track record.

The official XML remains a point product. The separately published CSDI
spatial package was also checked rather than assuming that "spatial" meant an
area layer. On the observation date its current GML was empty because HKO had
no listed system. The public archive contained quarterly snapshots from 2023
through 2026; every non-empty snapshot represented its records as
`gml:Point`. The 2026-10-01 snapshot, for example, contained point features for
past positions, one analysis position, and forecast positions, with no GML
polygon, surface, curve, or Potential Track Area feature. This corroborates
the track XML contract and does not provide an official area geometry for the
library to normalize.

No production parser or public data shape changed. HKO continues to expose
`observed_track`, a `forecast_track` built only from `ForecastInformation`
blocks carrying both a valid time and a numeric provider `Index`, and the same
restrained structured Forecast points. The fixture now also proves that an
unparseable index, a time without an index, and an index without a time cannot
become a forecast fix or inferred lead. Untimed smooth display vertices remain
outside the timed track contract, and neither the documented radius table nor
the point features manufacture a cone or `potential_track_area` geometry.

For the later Wevva handoff, the existing HKO map track and structured forecast
rows remain unchanged. There is no HKO area geometry for a generic consumer to
render, and no downstream presentation code should reconstruct one from the
published radius table. The separate `forecast_curve` vocabulary decision
remains in task 0017.

Slice 5 completed on 2026-11-08 as an evidence-backed no-go for adding a
structured PAGASA track. The current official bulletin page explicitly reported
no active tropical cyclone within PAR while PAGASA's daily weather page listed
Severe Tropical Storm CEMPAKA outside PAR. The severe-wind application likewise
rendered `No Active Severe Wind Impact-Based Forecast`. In that state it
published no typhoon selector or typhoon ID with which to address the candidate
track endpoint.

The site's current combined JavaScript still contains calls to
`POST /api/track_points/<typhoon-id>`, but that code path does not establish a
usable current lifecycle contract by itself. A public archive capture of the
official severe-wind page from 2026-07-08, when Tropical Depression IN-DAY had
an active product, rendered an iframe for `SWIBF#1_inday.pdf`; it did not expose
a structured typhoon ID, selector, or track response in the page. Later public
captures on 2026-08-10 and 2026-10-27 showed the explicit inactive state. The
PDF was deliberately not parsed.

This evidence confirms an active-to-inactive presentation lifecycle, but not
the candidate API contract required by this task. There are not two captured
structured updates, a stable discoverable identifier, or an observed
structured ended-state transition. Guessing database IDs, treating a dormant
JavaScript route as a supported feed, or extracting a track from the SWIBF PDF
would all cross the source-reliability boundary. No production code, public
data shape, fixture, or source registration changed.

The existing `pagasa_tropical` adapter remains the correct bounded source. It
uses the server-rendered current Tropical Cyclone Bulletin, respects PAGASA's
explicit no-active state, retains useful current facts and the bulletin as a
lazy product, and creates no track, cone, or wind geometry from prose. For the
later Wevva handoff, PAGASA therefore remains a current point observation plus
bulletin document, not a structured forecast-track provider. A future track
implementation requires a new active-event review demonstrating a discoverable
ID and stable anonymous responses across updates and withdrawal.

Slice 6 completed on 2026-11-07 without adding a provider. IMD's documentation
confirms that its native cyclone interfaces are unusually useful structured
sources: the track endpoint separates observed and forecast positions, and the
wind-warning and cone endpoints publish explicit `MultiPolygon` geometry. The
documented endpoints are `/api/v1/cyclone_track`, `/api/v1/cyclone_wind`, and
`/api/v1/cyclone_cou`. All three returned HTTP 401 without credentials during
this review. IMD's API portal offers account registration and describes
controlled key-based consumption, so this library does not register, add API
key configuration, share a maintainer key, or fall back to IMD's PDF or image
products. This is a credential-based no-go, not a claim that the native data
is unsuitable.

WMO SWIC's browser-facing tropical JSON is anonymous, structured, and covered
by useful reuse terms. WMO says the information is based on advisories from
RSMCs, TCWCs, and NMHSs, is free for reuse, and must be attributed to the
respective issuing centre. Its active index supplies an overall update time
and, per primary event, a `sysid`, start and latest times, centre IDs, GTS
references, and optional `same` links to separate centre-specific records.
Each per-system document retains its own `center_id`, analysed positions and
times, forecast positions, explicit forecast intervals, intensity, motion,
pressure, wind and gust values, and compact native wind-radius facts. The
official client maps those IDs to named centres and treats the interval as an
explicit hours-and-minutes offset. Neither the JSON nor the client supplies a
cone or wind-area polygon.

The live index at `2026-11-07 21:45:02` contained three primary events. Its
CEMPAKA entry related four still-separate observations from RSMC Tokyo,
Beijing, the Philippines, and Hong Kong; the individual JSON records retained
different positions, times, intensity values, forecasts, and centre IDs. This
is strong evidence that `same` is a presentation relationship, not permission
to collapse or relabel issuing-centre observations. The other current records
covered RSMC La Réunion and RSMC Honolulu. A public 2024-08-24 archive capture
used the same index field order for three different events, including separate
Tokyo and Beijing records for SHANSHAN. Those ended IDs are absent from the
current index and their old per-system URLs now return 404, confirming that
consumers must follow the active index and tolerate detail withdrawal.

That evidence is not yet enough for the proposed India/global-gap source. No
current RSMC New Delhi (`center_id` 6) system was available, no successive
snapshots of one active `sysid` were captured, and no actual empty
`tc_inforce.json` response could be recovered. The table client explicitly
handles an empty `inforce` array as its quiet state, but code showing the
intended behavior is weaker than an observed payload. The site's timeshift
client constructs archived tropical JSON paths, but sampled paths returned
404 during this review. Consequently stable identity across updates, an
observed New Delhi field/unit example, and the complete active-to-empty
lifecycle remain unverified.

SWIC is therefore a documented not-ready outcome rather than a new source or a
new numbered implementation task. Reconsider it during an active RSMC New
Delhi event only after capturing at least two index/detail updates and the
withdrawal or quiet transition. Any later implementation must emit each
centre's observation separately, preserve and expose its issuing-centre
identity, prefer existing direct providers rather than replace them, derive
forecast leads only from numeric `time_interval` values, keep non-numeric
presentation vertices out of timed forecasts, and retain compact wind radii as
provider facts without manufacturing geometry. No production code, fixture,
public model, source registration, or Wevva consumer contract changed in this
slice.

The release handoff completed in `v0.6.0`. The annotated `v0.6.0` tag identifies
the release commit and version intended for Wevva. That boundary includes the
completed JMA and CMA structured-detail changes, the HKO regression coverage,
and the separately implemented NHC/CPHC explicit GIS asset and discrete-fix
work needed by the downstream screen. It does not claim the still-deferred NHC
wind-field geometry from task 0005. Before tagging, the complete 230-test suite,
`compileall`, distribution build, and diff checks passed from the intended
tree. Wevva can now replace its editable sibling dependency with this released
version before beginning its separate structured-product presentation work.
