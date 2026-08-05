# Architecture

## Scope and public boundary

`wevva-warnings` normalizes official weather-warning products from a built-in
source registry. It is a synchronous, standard-library HTTP client with an
optional `curl` fallback; it is not a polling service or a general weather API.

The public Python boundary is `wevva_warnings/__init__.py`:

- `get_alerts_for_point()` and `get_alerts_for_source()` return `Alert`.
- `get_tropical_systems_for_source()` and `get_tropical_systems_near()` return
  `TropicalSystem`.
- `list_sources()`/`list_tropical_sources()`, `WarningSource`, `Alert`,
  `TropicalSystem`, geometry-resolution helpers, and the documented exceptions
  are also exported.

The `wevva-warnings` console script in `cli.py` is a second public interface.
Everything under `backends/`, the registry mapping, and parsing helpers are
implementation details even where names are not underscore-prefixed.

## Query and normalization flow

```text
country code + optional language
        -> sources.py registry -> registry.py backend
        -> provider adapter -> Alert / TropicalSystem
        -> source_info attached
        -> explicit geometry, or packaged geocode geometry
        -> point match, active filter, deduplication -> caller / CLI
```

`query.get_alerts_for_point()` selects alert sources by country and language.
English-capable sources are preferred by default; an unsupported requested
language warns and falls back to default selection. `nws` is the only current
backend with `uses_native_point_query=True`. All other alert backends are
filtered locally: an alert without `Polygon`/`MultiPolygon` geometry (explicit
or resolvable) cannot match a point and is skipped.

`get_alerts_for_source()` fetches an entire source, resolves geometry where
possible, and deduplicates only `(source, id)`. Point queries additionally
deduplicate semantically identical overlapping warnings. `active_only` uses
`Alert.is_active()` and UTC-normalized timestamps.

Tropical sources are separate from country routing. A system matches a
proximity query when its centre is within the radius or the point is in one of
its polygon geometry layers.

## Point-query progress

`get_alerts_for_point(..., progress=callback)` optionally calls a
`WarningQueryProgress` callback with `(event, payload)`. Calls are synchronous
and context-local: a caller that runs the query in a worker receives callbacks
on that worker thread and is responsible for scheduling any UI update. Callback
exceptions are ignored. Progress is advisory and does not change query,
filtering, deduplication, language, or error behaviour.

| Event | Payload | When emitted |
| --- | --- | --- |
| `query_started` | `country_code`, `lat`, `lon` | A point lookup begins, before source selection. |
| `sources_total` | `total` | Eligible alert sources have been selected. |
| `source_started` | `source`, `provider_name` | One source is about to be queried. |
| `alerts_total` | `source`, `total`, `phase` | A backend discovers country-wide CAP documents or geometry work items, or the query begins local matching. `phase` is `documents`, `geometry`, or `matching`. |
| `alerts_checked` | `source`, `completed`, `total`, `phase`; `matched` for `matching` | One document, geometry, or normalized alert has been processed. |
| `source_finished` | `source`, `candidates`, `matched`, `skipped_without_geometry`, `inactive_filtered` | A provider's fetch and local filtering have finished. |
| `finished` | `alert_count` | The successful query has completed its final deduplication. |

The same source can emit an early `alerts_total` while it fetches linked CAP
documents and a later `matching` total after normalization; the latter is the
authoritative count of candidate `Alert` objects. Native point-query backends
and feeds without individually fetchable documents can report only that later
count.

## Models and geometry

`models.Alert` carries common alert content, timing, area names, raw grouped
`geocodes` and `parameters`, optional GeoJSON geometry, and `source_info`.
`TropicalSystem` carries storm-specific fields plus named geometry layers and
data URLs. These fields intentionally retain provider-specific information.

`cap.parse_cap_alert()` is the common CAP 1.2 normalization path: it chooses a
requested-language `info` block (then English, then first), preserves CAP
geocodes/parameters, converts CAP `lat,lon` polygons to GeoJSON `lon,lat`, and
approximates CAP circles as polygons. `geometry.point_in_geometry()` supports
only `Polygon` and `MultiPolygon`, including holes and optional bounding-box
prefiltering.

`geocoding.py` fills missing warning geometry from packaged, lazily loaded
artifacts only: Meteoalarm EMMA IDs and aliases, Australian BoM
`AMOC-AreaCode`, and JMA area codes. It does not make runtime requests for
boundaries. The build scripts in `scripts/` produce those artifacts.

## Providers

`sources.py` is the source-of-truth inventory: at the time this document was
added it declares 159 enabled sources (155 alert, 4 tropical-system) across
84 backend IDs. Use `wevva-warnings sources` or `list_sources()` for the
current list; do not duplicate that volatile inventory here.

The provider implementations fall into these concrete families:

| Family | Current implementations | Behaviour and provider-specific boundary |
| --- | --- | --- |
| Native JSON point query | `nws` | Sends the point upstream and maps NWS GeoJSON features directly. The query layer trusts its native spatial filtering. |
| Structured or product-specific feeds | `geomet`, `ea_flood`, `hko`, `hydromet_guyana`, `meteoalarm_atom`, `nhc_gis`, `jma`, `jma_tropical` | Parse provider JSON/XML, RSS/Atom or GIS products directly. These adapters hold the source-specific field, URL, geometry, revision, or product-selection rules. `nhc_gis` and `jma_tropical` produce `TropicalSystem`. |
| Generic CAP | `generic_cap` (18 registered sources) | Accepts direct CAP, embedded CAP, RSS, or Atom and follows likely CAP links. Use only when the feed's link discovery works without provider rules. |
| Focused CAP feed adapters | the remaining alert backends | Fetch a provider feed, select the provider's CAP URLs, then use `_cap_feed.fetch_cap_documents()` and `cap.parse_cap_alert()`. Their small differences are intentional: link location/type, language, fixed or query-style URLs, archive/revision filtering, and area-name cleanup vary by provider. |

The shared CAP helpers are the meaningful existing abstraction: `base.py`
centralizes HTTP/JSON and error handling; `_cap_feed.py` centralizes feed XML,
URL resolution, linked-document retrieval, and CAP parsing; `generic_cap.py`
handles the broad standard case. Individual CAP adapters duplicate a small
amount of entry traversal, but it exposes each provider's fragile feed rule
locally. There is not evidence here for a broader provider framework.

Every backend subclasses `WarningBackend` and implements `fetch_alerts()`;
tropical providers additionally override `fetch_tropical_systems()`. A source
needs a stable ID, backend ID, kind, and truthful optional country/language
metadata; global sources deliberately have no country code. Non-native alert
providers also need explicit polygonal geometry or supported geocodes for point
lookup to be useful.

## External dependencies and constraints

Runtime dependencies are `pyshp`, `rich`, and `typer`; network calls are made
with `urllib`, with `curl` fallback when available. Providers are external,
mutable official services, so a failed request normally produces no alerts
from that backend rather than a library-wide exception.

The repository intentionally packages derived boundary artifacts rather than
large upstream inputs. Treat geometry data changes as behaviour changes: keep
the builder, artifact format, resolver, and fixtures aligned. Do not infer a
country from coordinates, silently route tropical sources through country
queries, or flatten provider metadata away merely to make results look alike.
