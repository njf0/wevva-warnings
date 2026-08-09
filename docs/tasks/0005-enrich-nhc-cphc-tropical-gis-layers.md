# Task 0005: Enrich NHC/CPHC tropical GIS systems with high-value layers

## Status

Proposed

## Target repository

`../wevva-warnings`

## Context

The NHC/CPHC GIS RSS sources are the strongest current tropical implementation.
They already group RSS assets by ATCF ID and return a centre, forecast track,
cone, and watch/warning geometry. The RSS feeds also advertise storm wind
fields, forecast products, and an ATCF XML advisory summary. The current
backend records several of their URLs but fetches geometry only for the three
KMZ layers.

NHC's official RSS documentation lists advisory track, cone, watches/warnings,
wind field, wind-probability, and storm-surge GIS products. The exact assets
available vary by advisory and basin.

## Problem

Consumers receive useful context but not some of the most important
machine-readable impact layers. `max_wind` is also available on the public
model but not currently populated by the NHC backend. The implementation must
improve this without treating all GIS layers as interchangeable polygons.

## Desired outcome

Extend the focused NHC GIS backend to expose selected additional official data
that is reliable, available in the active RSS feed, and directly useful to a
storm-centric consumer—starting with wind-field geometry and authoritative
advisory intensity fields where the XML explicitly provides them.

## Scope

- Inspect current and archived NHC/CPHC RSS products and choose a deliberately
  small set of additional supported assets.
- Parse the official wind-field product into one or more clearly named
  geometry layers, preserving any published wind-speed threshold or advisory
  metadata in `parameters`.
- Use the linked ATCF/advisory XML only when it supplies explicitly labelled
  fields such as maximum sustained wind; retain the source value and unit.
- Keep unparsed/optional assets in `data_urls` so callers can still inspect
  them without the library pretending to normalize them.
- Handle KMZ, KML, zipped shapefile, or other format variations only when
  verified against the selected asset. Use the existing `pyshp` dependency
  rather than adding a GIS stack.
- Add provider fixtures for each new supported asset and update source/API
  documentation with the named layers and their limits.

## Non-goals

- Do not parse every NHC GIS asset or build a generic GIS download framework.
- Do not infer maximum wind from a headline or scrape an HTML advisory.
- Do not merge wind fields, cones, and official watches/warnings into one
  geometry or severity.
- Do not make tropical systems part of ordinary country alert routing.
- Do not add live-network tests.

## Relevant code

- `wevva_warnings/backends/nhc_gis.py`
- `wevva_warnings/backends/base.py`
- `wevva_warnings/models.py`
- `wevva_warnings/geometry.py`
- `tests/test_provider_backends.py` and NHC GIS fixtures
- `README.md`, `docs/architecture.md`, and `TROPICAL_SYSTEMS.md`

## Approach

1. Capture representative official archived and active RSS/KMZ/shapefile/XML
   samples outside the test suite. Record which asset variants are stable
   enough to support.
2. Add narrowly scoped parsing helpers to `nhc_gis.py` for those variants.
   Each helper should return a named geometry or explicitly decline unsupported
   content without failing the system result.
3. Preserve the existing ATCF grouping and all currently returned layers.
   Add new geometry keys only where their semantics and source metadata are
   clear.
4. Parse intensity only from labelled XML fields and preserve raw values. Keep
   an unavailable or malformed field as `None` rather than guessing.
5. Ensure task 0004's match-evidence API can identify a wind-field containment
   layer without calling it a watch/warning.

## Acceptance criteria

- Existing NHC/CPHC track, cone, and watch/warning results remain unchanged.
- A fixture with a supported wind-field asset returns a named usable geometry
  layer and retains its threshold/advisory metadata.
- A fixture with an authoritative maximum-wind value populates `max_wind` with
  the published unit; a fixture without it leaves the field unset.
- Missing, malformed, or unsupported optional assets do not discard the storm
  object or its existing geometry.
- `data_urls` retains optional links that are not parsed.
- The documentation distinguishes every supported geometry layer from an
  official warning area.

## Verification

- Add mocked RSS, advisory XML, and selected GIS asset fixtures; no test may
  call NHC or CPHC live.
- Cover successful and malformed optional asset handling, multiple wind
  thresholds where supported, and preservation of existing layers.
- Run `uv run python -m unittest discover -s tests -v`.

## Decisions and notes

- Prefer a few well-understood layers over nominal support for the whole NHC
  GIS catalogue.
- Reassess other NHC products, such as storm surge, in a separate task after
  their geographic and temporal semantics are established.

## Outcome

Not started.
