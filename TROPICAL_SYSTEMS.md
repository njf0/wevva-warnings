# Tropical Systems Note

This note captures the current thinking around tsunami and tropical cyclone
products, and how they likely fit into `wevva-warnings` versus the downstream
`wevva` app.

## Summary

Tropical cyclone and tsunami feeds are not always a good fit for the existing
`Alert` model or the current country-routed point-query API.

They are still valuable, but they often behave more like:

- basin or ocean-region products
- storm objects with multiple spatial layers
- offshore or coastal risk products
- advisory systems that may matter well beyond one country's boundaries

So the likely long-term direction is:

- keep ingesting official machine-parseable feeds
- do not force all of them into ordinary land-warning semantics
- add a separate model and query path for tropical systems

## What We Learned

### NOAA NTWC / PTWC tsunami

The NOAA tsunami feeds are official and machine-parseable.

- `NTWC` publishes an Atom feed with linked CAP documents
- `PTWC` also has a direct CAP endpoint
- these are suitable for source-level ingestion right now

However, the spatial geometry may be thin.

In the live `NTWC` CAP sample we inspected:

- the alert had a CAP `area`
- the geometry was a CAP `circle`
- the circle radius was `0.0`

So geometry technically exists, but it can behave like an exact epicenter match
rather than a useful affected-area polygon.

That makes these feeds more useful for:

- `get_alerts_for_source(...)`
- source inspection
- future ocean-region / offshore logic

than for ordinary country point queries.

### NHC / CPHC tropical cyclone products

NHC-style tropical cyclone products usually have much richer spatial structure,
but not in the same shape as a normal CAP warning polygon.

Useful geometry products can include:

- storm center point
- forecast track
- cone of uncertainty
- wind radii / wind-field geometry
- watches and warnings
- breakpoint-based coastal warning extents

So these are highly machine-parseable, but they are best treated as
storm-centric GIS products rather than ordinary warning polygons.

### JMA

JMA is a strong fit for code-plus-GIS handling.

- JMA XML products use official area codes
- JMA also publishes official GIS datasets for those codes

That is a good model for Japan's tsunami and other hazard products:

- bulletin carries official area codes
- geometry comes from the official GIS layer

### BoM tropical cyclone products

BoM cyclone products also look more like storm/advice/track-map products than
generic CAP warning polygons.

The useful spatial concepts are likely to be:

- track maps
- watch/warning zones
- wind radii
- cyclone-specific XML products

## Why `Alert` Is Not Enough

The existing `Alert` model works best for:

- a single normalized warning
- with a headline, severity, timing, and one geometry concept

Tropical cyclone systems are often better represented as:

- one storm object
- with multiple geometry layers
- updated through numbered advisories
- relevant across multiple countries and marine areas

Trying to squeeze that into `Alert` would likely make the model muddier over
time.

## Proposed Model

Add a separate dataclass, probably named `TropicalSystem`.

`TropicalSystem` is preferred over `TropicalStorm` because it can also cover:

- tropical depressions
- hurricanes / typhoons / cyclones
- subtropical systems
- named or unnamed systems

Likely fields:

- `id`
- `source`
- `basin`
- `name`
- `classification`
- `advisory_number`
- `issued_at`
- `center_lat`
- `center_lon`
- `movement`
- `max_wind`
- `min_pressure`
- `headline`
- `summary`
- `track_geometry`
- `cone_geometry`
- `wind_field_geometries`
- `watch_warning_geometries`
- `raw_area_segments`
- `url`

Not every provider will populate every field, which is fine.

## Proposed Query Model

Do not route tropical systems only by `country_code`.

The current warning query model:

- `get_alerts_for_point(lat, lon, country_code, ...)`

is a good fit for land warnings, but not for ocean-basin storm products.

For tropical systems, a better shape is something like:

- `get_tropical_systems_near(lat, lon, radius_km=...)`
- `get_tropical_systems_for_basin(...)`
- `get_tropical_systems_for_region(...)`

This matters because users may care about nearby offshore threats even when the
issuing authority is in another country.

Examples:

- a user in Singapore may care about Australian-region tropical systems
- a Caribbean user may care about NHC systems spanning many countries
- a coastal user may want "scary things happening out at sea", not just
  "warnings whose polygon contains my home"

## Separation of Responsibilities

Recommended split:

- `wevva-warnings`
  - ingest official machine-parseable sources
  - normalize warning products
  - expose storm-centric products cleanly where needed

- `wevva`
  - build higher-level app logic
  - decide what counts as "nearby" or "scary"
  - combine offshore systems, coastal alerts, and local warnings into one UX

This lets the library stay clean without losing useful storm/ocean products.

## Current Practical Direction

Short term:

- continue accepting official machine-parseable tsunami / cyclone sources
- be comfortable if some are initially better for `source` queries than for
  `point` queries
- avoid pretending weak geometry is stronger than it is

Medium term:

- add a `TropicalSystem` model
- add separate tropical-system query helpers
- build dedicated backends for NHC/CPHC-style storm products

Long term:

- support richer spatial reasoning:
  - distance to storm center
  - proximity to forecast cone
  - proximity to wind fields
  - coastal / offshore threat display

## Rule of Thumb

For this repo, tropical products should be treated as:

- valid and important
- often machine-parseable
- sometimes poor fits for ordinary point-in-polygon warning logic

That is not a problem. It just means they deserve a parallel model rather than
being bent into the existing one.
