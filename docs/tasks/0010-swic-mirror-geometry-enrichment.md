# Task 0010: Enrich geometry-less SWIC mirror alerts

## Status

Complete

## Context

China Meteorological Administration alerts are consumed through WMO Severe
Weather Information Centre (SWIC) RSS/CAP mirrors. CMA CAP documents commonly
contain a CPEAS administrative-area code but no CAP polygon. The WMO SWIC map
also publishes the corresponding warning geometry through its WFS endpoint.

## Problem

An alert without polygonal geometry cannot be locally matched to a point. This
makes otherwise valid CMA warnings unusable by consumers that cache the
library's reusable country candidates and later call
`match_alerts_to_point()`.

## Desired outcome

When a SWIC-mirror CAP alert lacks geometry, the existing backend should
best-effort backfill its polygon from the WMO SWIC WFS map feature with the
same CAP URL. Callers retain the existing public query and local-match APIs.

## Scope

- Add batched WFS geometry lookup to the existing `swic_mirror` backend.
- Match WFS data by exact relative CAP URL, not country/provider names or
  alert text.
- Preserve CAP geometry when it is already available.
- Combine multiple WFS polygon features for one CAP document into a valid
  `MultiPolygon` and record concise geometry provenance in `parameters`.
- Treat WFS failure, malformed data, and missing rows as non-fatal.
- Add deterministic unit tests and concise source/architecture documentation.

## Non-goals

- No new cache, public query API, generic geocoding framework, or downstream
  `wevva` change.
- No special case for China or any named provider.
- No runtime changes to `geocoding.py` or packaged-boundary workflows.

## Relevant code

- `wevva_warnings/backends/swic_mirror.py`
- `wevva_warnings/cap.py`
- `wevva_warnings/geometry.py`
- `wevva_warnings/sources.py`
- `tests/test_provider_backends.py`
- `docs/architecture.md`

## Approach

1. Fetch and parse the SWIC RSS/CAP documents as today.
2. Extract the source's validated SWIC feed prefix and request only the exact
   CAP URLs fetched without geometry, in small WFS batches.
3. Keep only WFS features whose `capurl` exactly matches a requested CAP URL.
4. Resolve supported packaged geometry first, then attach normalized polygonal
   WFS geometry only to alerts that still have none; leave all other alert
   content untouched.
5. Return raw CAP alerts unchanged if enrichment is unavailable.

## Acceptance criteria

- A geometry-less SWIC CAP alert receives usable `Polygon`/`MultiPolygon`
  geometry from matching WFS features.
- Multiple matching WFS polygons are retained.
- Existing CAP geometry is never replaced.
- Unrelated WFS rows cannot be attached.
- Fetch failures do not suppress CAP alerts or alter progress semantics.
- Local `match_alerts_to_point()` can use enriched geometry without network
  access.

## Verification

```bash
uv run python -m unittest discover -s tests -v
uv build
```

## Decisions and notes

- The WFS lookup is a fetch-time source enrichment, not geocoding and not a
  point-query backend.
- CAP is authoritative for alert content. WFS is used only for a missing
  polygon, and its provenance remains visible on the alert.
- Exact CAP URL matching avoids relying on unstable translated place names or
  domestic administrative coding.

## Outcome

Implemented in the existing `swic_mirror` backend. Geometry-less CAP alerts
now prefer matching packaged geocode geometry and then receive matching WMO
SWIC WFS polygons through bounded exact-CAP-URL batches. CAP geometry remains
authoritative and WFS failure returns the raw alert. No public API or
downstream matching change was required.

Verified with the deterministic provider suite, the complete unit-test suite,
the WMO WFS filter, and `uv build`.
