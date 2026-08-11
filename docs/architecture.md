# Architecture

## Scope and public boundary

`wevva-warnings` normalizes official weather-warning products from a built-in
source registry. It is a synchronous, standard-library HTTP client with an
optional `curl` fallback; it is not a polling service or a general weather API.

The public Python boundary is `wevva_warnings/__init__.py`:

- `get_alerts_for_point()`, `get_alerts_for_country()`,
  `get_reusable_alerts_for_country()`, `get_native_alerts_for_point()`, and
  `get_alerts_for_source()` return `Alert`; `deduplicate_alerts()` combines
  locally matched and native results using point-query deduplication rules.
- `get_swic_extreme_alerts()` returns global WMO SWIC mapped Extreme-warning
  discovery candidates as `Alert` objects. It is not country routing.
- `get_alert_sources_for_country()` exposes point-query source selection, and
  `match_alerts_to_point()` matches fetched candidates locally.
- `get_tropical_systems()`, `get_tropical_systems_for_source()`,
  `match_tropical_systems_to_point()`, and `get_tropical_systems_near()`
  return `TropicalSystem`.
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

`get_alerts_for_country()` retains its broad country-level behaviour for
existing callers: it selects every eligible source, fetches each without point
coordinates, attaches `source_info`, resolves available packaged geometry,
filters active alerts when requested, and deduplicates `(source, id)` per
source. It does not promise a complete country inventory when an upstream
source cannot deliberately provide one. Its results are not necessarily safe
to cache as local candidates because native point-query sources are included.

`get_reusable_alerts_for_country()` has the same country/language, active, and
country-progress semantics, but selects only backends whose
`uses_native_point_query` capability is false. Its results are safe reusable
inputs to `match_alerts_to_point()`. `get_native_alerts_for_point()` applies
the complementary true capability filter, passes the point to only those
backends, and follows the usual point-query progress event contract. A caller
combines local matches with native results through `deduplicate_alerts()`,
which first deduplicates `(source, id)` and then applies normal semantic
point-query deduplication. The split is capability-driven; it contains no
provider- or country-specific routing.

`match_alerts_to_point()` makes no network calls. It resolves missing supported
packaged geometry on the supplied `Alert` objects, drops alerts without usable
geometry, applies `active_only`, performs source/ID deduplication, then uses
the same semantic deduplication as point queries. Applications own cache
lifetimes and should normally cache country candidates without `active_only`
when later matching at different times matters. `deduplicate_alerts()` makes
no network calls or active-time decision; callers apply `active_only` when
matching cached candidates and querying native sources.

Tropical sources are separate from country routing. A system matches a
proximity query when its centre is within the radius or the point is in one of
its polygon geometry layers. A tropical source may declare
`issuer_country_code`, the ISO 3166-1 alpha-2 location of its operational
issuing centre. It is a downstream presentation-priority hint, not a coverage
claim: applications may rank same-location issuers first among systems already
matched to a point, but must never use it to filter foreign regional systems.

`get_tropical_systems()` fetches raw current reports from all tropical sources,
or the explicit `source_ids`, without sending or applying a point. Its output
is safe for an application-owned short-lived cache, including one cache entry
per source. `match_tropical_systems_to_point()` then applies the same local
centre-radius and polygon-layer rules as the one-call
`get_tropical_systems_near()` helper, including `(source, id)` deduplication.
It makes no network requests. The library owns neither a cache nor tropical
country routing; applications must keep tropical reports separate from ordinary
country-warning candidates.

### Tropical and offshore products

`TropicalSystem` is a storm-centric model rather than a second kind of land
warning. It holds available current facts such as classification, name, basin,
advisory number, issue time, centre, motion, wind and pressure, alongside
provider URLs, named geometry layers, and source-specific values in
`parameters`. Fields may be absent where an official product does not provide
them; the library does not infer them from a track or headline.

Tracks, cones, wind fields, and watches or warnings are distinct provider
concepts. Backends retain their named layers instead of flattening them into
one generic warning polygon. A downstream UI may show a storm near a location,
but must not present a forecast track or cone as a local official warning.
Tropical systems can be relevant across national boundaries, which is why the
separate proximity query deliberately checks regional providers rather than
using country-source routing.

The NTWC and PTWC tsunami products remain ordinary `Alert` sources, but are
also global/offshore feeds rather than country-routed providers. Their CAP
geometry can be too limited for a useful local match (for example, a
zero-radius circle). Preserve and expose the official product, but do not
invent broader affected-area geometry from an epicentre or text alone.

`get_swic_extreme_alerts()` is a separate global discovery path. It requests
WMO SWIC WFS map features whose severity code is `4`, groups polygon rows by
their exact mirrored CAP URL, and returns a normal `Alert` for each group. The
helper locally applies its default `active_only=True` filter and excludes WFS
rows marked as marine unless requested. It does not fetch country feeds,
participate in country source selection, or emit the point/country progress
events. WMO SWIC map coverage is not a complete inventory of worldwide
warnings; the resulting candidates are intended for an application to rank or
select.

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

### Country-query progress

`get_alerts_for_country(..., progress=callback)` uses the same synchronous,
exception-safe callback behaviour. It emits `country_query_started` with
`country_code`, followed by the reusable `sources_total`, `source_started`,
and any backend `alerts_total`/`alerts_checked` document or geometry events.
It then emits `country_source_finished` with `source`, `candidates`, and
`inactive_filtered` for each source, and `country_finished` with the final
`alert_count`. Country completion events are distinct so the point-query
meaning of `matched` remains unchanged. For
`get_reusable_alerts_for_country()`, `sources_total` and subsequent per-source
events cover only non-native sources.

### Tropical proximity progress

`get_tropical_systems_near(..., progress=callback)` uses the same synchronous,
context-local, exception-safe `WarningQueryProgress` callback type, but emits
only the following tropical-specific events. It does not reuse ordinary alert
event names, and backend-level alert progress events are not forwarded through
this public callback.

| Event | Payload | When emitted |
| --- | --- | --- |
| `tropical_fetch_started` | `lat`, `lon`, `source_total` | The proximity query has selected tropical sources with available backends. |
| `tropical_source_started` | `source`, `provider_name` | One selected tropical source is about to be fetched. |
| `tropical_source_finished` | `source`, `candidates` | That source has returned normalized tropical-system candidates. |
| `tropical_check_total` | `total` | All selected sources have returned; `total` is the exact number of candidates to check locally. Emitted once. |
| `tropical_checked` | `completed`, `total`, `matched` | One candidate has been checked. `matched` is the cumulative proximity-match count before `(source, id)` deduplication. |
| `tropical_finished` | `system_count` | The final source/ID-deduplicated result list is ready. |

All fetch events precede `tropical_check_total`. After that event, only
`tropical_checked` events and `tropical_finished` are emitted. A zero-candidate
query still emits `tropical_check_total(total=0)` followed by
`tropical_finished(system_count=0)`. The existing matching rule, source-ID
filtering, debug logging, source/ID deduplication, and return value remain
unchanged when `progress` is omitted. The one-call helper fetches source-wide
reports and performs its point match locally, just as the two-stage public
tropical helpers do; only `get_tropical_systems_near()` has this progress
callback contract.

## Models and geometry

`models.Alert` carries common alert content, timing, area names, raw grouped
`geocodes` and `parameters`, optional GeoJSON geometry, and `source_info`.
`TropicalSystem` carries storm-specific fields plus named geometry layers and
data URLs. These fields intentionally retain provider-specific information;
the tropical/offshore boundary above explains why their semantics must not be
collapsed into ordinary land-warning matching.

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

The `swic_mirror` backend has a separate fetch-time enrichment for a SWIC map
source: after CAP parsing, it first resolves supported packaged geocodes, then
may use WMO's WFS map data to backfill geometry still missing. It joins only
on the exact CAP URL selected from that source's RSS feed, preserves a
CAP-provided or packaged polygon, and records WFS provenance in
`Alert.parameters`. This is neither geocoding nor point matching: once the
alert has been returned, `match_alerts_to_point()` remains local and makes no
network request.

## Providers

`sources.py` is the source-of-truth inventory: at the time this document was
added it declares 171 enabled sources (162 alert, 9 tropical-system) across
89 backend IDs. Use `wevva-warnings sources` or `list_sources()` for the
current list; do not duplicate that volatile inventory here.

The provider implementations fall into these concrete families:

| Family | Current implementations | Behaviour and provider-specific boundary |
| --- | --- | --- |
| Native JSON point query | `nws` | Sends the point upstream and maps NWS GeoJSON features directly. The query layer trusts its native spatial filtering. |
| Structured or product-specific feeds | `bom_tropical`, `cma_tropical`, `geomet`, `ea_flood`, `hko`, `hydromet_guyana`, `jma`, `jma_tropical`, `meteoalarm_atom`, `meteofrance_reunion_tropical`, `nhc_gis`, `pagasa_tropical`, `swic_mirror`, `swic_extreme` | Parse provider JSON/XML, RSS/Atom, HTML, or GIS products directly. These adapters hold the source-specific field, URL, geometry, revision, or product-selection rules. `cma_tropical` defensively unwraps the NMC Typhoon Network's browser-facing JSONP and uses only systems marked current. `pagasa_tropical` accepts only the live bulletin page, never its archive links. `swic_mirror` can add a matching WMO map polygon when CAP has none; `swic_extreme` groups global WFS features for the explicit discovery helper. `nhc_gis`, `jma_tropical`, `cma_tropical`, `pagasa_tropical`, `bom_tropical`, `hko`, and `meteofrance_reunion_tropical` produce `TropicalSystem`. |
| Generic CAP | `generic_cap` (24 registered sources) | Accepts direct CAP, embedded CAP, RSS, or Atom and follows likely CAP links. Use only when the feed's link discovery works without provider rules. |
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
metadata. `country_code` is country-alert routing metadata; a tropical source
instead may supply `issuer_country_code` as its operational-centre location.
Global sources deliberately have no routing country code. Non-native alert
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
