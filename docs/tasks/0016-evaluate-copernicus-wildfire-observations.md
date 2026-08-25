# Task 0016: Evaluate Copernicus wildfire observations

## Status

Proposed

## Context

Copernicus Emergency Management Service operates the European Forest Fire
Information System (EFFIS). EFFIS publishes active-fire detections, burned
areas, and fire-weather data. Its public data-service page documents a
standards-based map service at
https://maps.effis.emergency.copernicus.eu/effis and states that map layers
are queryable by location.

An initial live compatibility check found:

- WMS active-fire layers including all.hs, viirs.hs, noaa.hs, and modis.hs;
- a linked WFS 1.1 GetFeature endpoint for all.hs, returning GML;
- point-record fields including id, acq_at, lon, lat, frp, confidence, night,
  satellite, scan, track, processing version, land-cover flags, country, and
  classification;
- a spatial BBOX request works. With WFS 1.1 EPSG:4326, this service expects
  BBOX coordinates in latitude, longitude axis order. The explicit lon and lat
  fields must be the canonical values after parsing.

EFFIS says its active-fire product is a filtered subset of NASA FIRMS thermal
anomalies, normally updated six times daily and available 2–3 hours after
acquisition. A detection is neither a confirmed wildfire nor an official
public-safety warning. See:

- https://forest-fire.emergency.copernicus.eu/about-effis/technical-background/active-fire-detection
- https://forest-fire.emergency.copernicus.eu/downloads-instructions
- https://forest-fire.emergency.copernicus.eu/about-effis/data-license

The Global Wildfire Information System (GWIS) is a later candidate for
worldwide coverage, but EFFIS is the first candidate because its vector
endpoint and record schema are already established. EFFIS’s documented
operational remit is Europe, the Middle East, and North Africa; do not
advertise broader coverage solely because an individual service layer has a
global bounding box.

## Problem

Callers can retrieve official weather warnings for a point, but cannot ask for
recent satellite-based wildfire observations near it. Forcing a point
detection into Alert would incorrectly present an observation as an
authority-issued warning and would not fit normal alert polygon matching.

## Desired outcome

After a compatibility spike, provide a clearly separate, opt-in API for recent
EFFIS active-fire detections near a supplied point. Results must preserve the
provider facts, state the observation limitations, and never be returned by
the existing warning query APIs.

## Scope

- Validate current EFFIS WFS availability, schema, filtering, and pagination
  against the public service.
- Add a focused EFFIS active-fire backend only if that validation establishes a
  bounded, reliable request for a small nearby area and a recent time window.
- Add a dedicated public model and a proximity helper, tentatively named
  WildfireDetection and get_wildfire_detections_near().
- Let callers select a radius in kilometres and a maximum observation age,
  with conservative documented defaults proposed by the spike.
- Use a bounding-box upstream query followed by an exact local great-circle
  distance check. The upstream BBOX alone is not a radius.
- Preserve the EFFIS record id, acquisition time, source layer/satellite,
  FRP, confidence, class, flags, raw properties, point geometry, source URL,
  and computed distance.
- Add fixture-based unit tests only; no live network checks in the test suite.
- Document coverage, freshness, attribution, licensing, and the difference
  between a detection and an official alert.

## Non-goals

- Do not add EFFIS or GWIS to sources.py, country warning routing, or any API
  that returns Alert.
- Do not claim that no returned detections means there is no fire.
- Do not infer a wildfire perimeter, severity, evacuation area, or public
  instruction from a hotspot.
- Do not add a polling service, background cache, account credentials, or a
  general geospatial dependency.
- Do not implement direct Sentinel-3 Fire Radiative Power product processing.
  It is a useful future provenance option, but it is lower-level than the
  EFFIS service and requires a separate product-access design.
- Do not add GWIS in the first implementation. Reassess it only after the
  EFFIS contract is proven and the project needs formal global coverage.

## Relevant code

- wevva_warnings/__init__.py — public API exports.
- wevva_warnings/models.py — Alert semantics and rich output conventions.
- wevva_warnings/query.py — warning routing and existing tropical proximity
  helper patterns. This task must not change warning routing.
- wevva_warnings/backends/base.py — HTTP helpers and backend conventions.
- wevva_warnings/backends/ — focused source adapters.
- tests/ — standard-library unittest fixtures and mocked HTTP payloads.
- docs/architecture.md — scope boundary, public model, and proximity-query
  documentation.
- README.md — user-facing capabilities and limitations.

## Approach

1. Run a bounded compatibility spike.
   - Request WFS GetCapabilities and DescribeFeatureType for the intended
     layer(s); record the supported response formats and full schema.
   - Verify a combined spatial and recent-time filter using several ordinary
     locations. A TIME parameter did not constrain an initial WFS request, so
     the backend must not rely on it without proof.
   - Determine whether a standard OGC Filter on acq_at is reliable for range
     queries. If not, measure the smallest safe spatial request and apply the
     time filter locally, with a strict response-size limit.
   - Verify feature limits/pagination, empty results, server error responses,
     layer differences, and normal request latency.
   - Confirm published retention, coverage, and update behaviour with EFFIS.
     The first successful WFS sample was historical, so currentness must be
     demonstrated independently before implementation.

2. Decide whether the upstream contract is safe enough.
   - Proceed only if recent records can be selected predictably and the
     returned volume is bounded for the chosen radius.
   - Otherwise stop after documenting the findings and evaluate GWIS or an
     official national source; do not ship an unbounded scraper.

3. Define the separate public contract.
   - Use a model whose name and documentation say detection or observation,
     never alert.
   - Include observed_at, location, distance_km, provider metadata, raw
     attributes, and a source URL. Make absent upstream values optional rather
     than synthesising them.
   - The proposed helper accepts latitude, longitude, radius_km, max_age, and
     optional source/layer selection. It returns a distance-ordered list.
   - Decide defaults only after measuring upstream completeness. A reasonable
     starting candidate is a 25 km radius and 24-hour maximum age, but those
     are not part of the contract until the spike confirms them.
   - State in the docstring and CLI output that results are satellite
     detections, can be false positives or missed, and are not safety advice.

4. Implement a small EFFIS adapter.
   - Build and percent-encode only bounded WFS requests. Respect the observed
     EPSG:4326 axis ordering and parse GML with the standard library.
   - Treat lon and lat record properties as authoritative point coordinates;
     retain the original geometry and raw provider fields for diagnostics.
   - Filter by exact geodesic distance, acquisition age, and any documented
     EFFIS wildfire qualification flags. Deduplicate on EFFIS layer plus id.
   - Fail closed on malformed records, unsupported schema changes, oversized
     responses, or unavailable service; do not turn provider errors into a
     false no-fire result.

5. Test and document.
   - Add deterministic GML fixtures for one valid detection, multiple
     detections at different distances/ages, no results, malformed properties,
     axis-order handling, duplicate ids, and WFS exceptions.
   - Test public exports and ensure all existing warning and tropical tests
     retain their behaviour.
   - Update README and architecture docs with the model boundary, coverage,
     attribution under EFFIS’s CC BY 4.0 terms, freshness caveat, and
     non-alert disclaimer.

## Acceptance criteria

- The project has a written, evidence-backed decision either to proceed or to
  reject EFFIS as an upstream service for nearby recent detections.
- If proceeding, a caller can retrieve and inspect recent detections near a
  point without changing any existing warning-query result.
- Every returned item identifies EFFIS and its acquisition time and contains
  the source point and computed proximity distance.
- A detection is never described or serialised as an official warning, and no
  negative result makes a no-wildfire claim.
- The backend has a deterministic maximum request scope and rejects
  unbounded/oversized upstream responses.
- Existing public exports and warning, geometry, progress, and tropical
  behaviour remain compatible.
- New parsing and proximity behaviour is covered with mocked fixtures and the
  full unittest suite passes.

## Verification

- Use live EFFIS requests only during the compatibility spike; record their
  date, layer, request shape, response schema, and observed limitations in
  this task’s Decisions and notes section.
- Run uv run python -m unittest discover -s tests -v after implementation.
- Manually inspect an example Rich/CLI representation to confirm that it says
  detection/observation and carries the source attribution and disclaimer.

## Decisions and notes

- Current recommendation: use the EFFIS WFS as the first feasibility target,
  not raw Sentinel-3 FRP products and not WMS pixel interrogation. WFS is
  vector-oriented and already exposes individual observation fields.
- A raw WFS record query and a spatial BBOX request succeeded on 2026-08-11.
  Equality filtering on id and acq_at also succeeded. A range comparison
  request returned an upstream HTTP 502, so recency range filtering remains
  a blocking spike question.
- EFFIS data is generally reusable under CC BY 4.0 unless otherwise
  indicated. Attribution and indication of modifications are required.
- The existing Alert model accepts point geometry for representation, but
  normal point-warning matching supports only Polygon and MultiPolygon. This
  confirms that a parallel wildfire-observation API is the correct boundary.

## Outcome

Not started.
