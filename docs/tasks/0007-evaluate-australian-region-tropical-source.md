# Task 0007: Evaluate an official Australian-region tropical source

## Status

Completed

## Target repository

`../wevva-warnings`

## Context

Current tropical coverage is limited to the Atlantic, Eastern Pacific, Central
Pacific, and Northwest Pacific. The original tropical systems note identified
Australian Bureau of Meteorology (BoM) tropical-cyclone products as a promising
next direction because they may provide track, watch/warning-zone, wind-radius,
or cyclone-specific machine-readable data.

Before adding a provider, the repository needs evidence that an official,
maintained, machine-readable source is suitable for a storm-centric public API.
An attractive public web page or image map is not sufficient.

## Problem

There is no documented decision on the next tropical basin/source. Adding a
backend speculatively risks a brittle scraper, weak location semantics, or a
source whose availability cannot be tested outside the cyclone season.

## Desired outcome

Produce a concise, evidence-backed source decision for the Australian region:
either identify one official BoM source ready for implementation, with sample
payloads and clear spatial semantics, or explicitly record why it should not
be added now and nominate the next official candidate.

## Scope

- Investigate official BoM tropical-cyclone data/services and their documented
  update, attribution, and access conditions.
- Prefer structured feeds, GIS services, XML/JSON, CAP, KML/KMZ, GeoJSON, or
  stable downloadable GIS products over HTML or image scraping.
- Verify the source has a stable current endpoint and obtain representative
  active or archived samples for at least a track/centre and any claimed
  impact layer.
- Identify basin/area coverage, language, identifiers, advisory timestamps,
  update/revision behaviour, and the exact meaning of each spatial product.
- Assess whether it is appropriate as a `TropicalSystem` source, an ordinary
  `Alert` source, both as separate products, or neither.
- Record the decision, selected endpoint, sample provenance, and proposed
  source ID/backend boundary in this task's Outcome or a short linked note.

## Non-goals

- Do not add a backend, registry source, or untested public API during this
  investigation task.
- Do not scrape BoM interactive maps, PDF graphics, or social-media posts.
- Do not assume an endpoint is usable merely because an archived storm page
  exists.
- Do not generalise the outcome into an all-basin provider framework.

## Relevant code

- `docs/architecture.md`
- `wevva_warnings/sources.py`
- `wevva_warnings/backends/nhc_gis.py`
- `wevva_warnings/backends/jma_tropical.py`
- `docs/architecture.md`

## Approach

1. Start from BoM's official developer, tropical-cyclone, and data catalogue
   material. Use primary documentation rather than third-party aggregators.
2. Test prospective endpoints read-only. Expect seasonal empty feeds and use
   official archives or documented examples to validate schema where needed.
3. Compare the result against the existing NHC and JMA adapters: stable storm
   ID, issue time, centre/track, named impact geometry, language, and handling
   of revisions are more important than the raw number of fields.
4. Write a go/no-go decision. A go decision must include an implementable
   fixture plan and exact semantics; a no-go decision must state the blocker
   and the next official candidate worth evaluating.

## Acceptance criteria

- The investigation names a specific official endpoint or documents a clear
  reason not to use one.
- The decision distinguishes storm context (centre/track/cone) from official
  local impact/warning geometry.
- Sample payloads or stable official archive references are identified for
  future deterministic tests without committing copyrighted bulk data blindly.
- A proposed implementation can name its `WarningSource` metadata, source ID,
  backend boundary, expected `TropicalSystem` fields, and known limitations.
- No production source or code changes are made solely to close this task.

## Verification

- Record URLs and checks performed in the Outcome.
- Confirm any proposed sample is official and can be transformed into a small,
  deterministic fixture in a later implementation task.
- Review the decision against the tropical/offshore architecture guidance and
  the provider-addition guidance in `AGENTS.md`.

## Decisions and notes

- BoM is the preferred candidate, not a pre-authorised implementation choice.
  The data quality decision takes precedence over geographic coverage.
- A seasonal empty response is normal and is not evidence of a broken source.

## Outcome

Go: use the Australian Bureau of Meteorology's public FTP forecast-track GML
products at `ftp://ftp.bom.gov.au/anon/gen/fwo/`.

The official [BoM warning-products guide](https://www.bom.gov.au/catalogue/Bureau_of_Meteorology_warning_products_user_guide.pdf)
documents the tropical-cyclone forecast-track products and their GML forms.
The current directory publishes a small set of stable, region-specific product
filenames; outside cyclone season it can legitimately contain none of them.
The official sample catalogue's `IDD65401.gml` demonstrated a stable
disturbance ID, name, issue time, current centre and category, plus forecast
track and explicitly labelled watch/warning/forecast/wind geometries.

This is suitable for a storm-centric source, but not for ordinary country
alerts: track and area layers are retained with their BoM meaning and no land
warning is inferred. Task 0008 implements the selected source as
`bom_tropical`.
