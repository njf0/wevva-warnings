# wevva-warnings

`wevva-warnings` is a small Python library and CLI for looking up official
weather warnings for a single point.

You provide `lat`, `lon`, and a `country_code`; the library picks the right
official source or sources, normalizes the returned alerts, and filters them by
native point query or geometry.

## Install

Python 3.12 or later is required.

```bash
pip install wevva-warnings
```

## Quick start

```python
from wevva_warnings import get_alerts_for_point

alerts = get_alerts_for_point(
    lat=40.71,
    lon=-74.00,
    country_code="US",
    active_only=True,
)

for alert in alerts:
    print(alert.headline)
    print(alert.url)
```

Language-specific feeds can be selected with `lang`:

```python
alerts = get_alerts_for_point(49.8, 7.67, "DE", lang="de")
```

```bash
wevva-warnings point 40.71 -74.00 US
```

```bash
wevva-warnings tropical-source nhc_gis_atlantic --formatted
```

## Key Python features

```python
from wevva_warnings import (
    deduplicate_alerts,
    get_alerts_for_point,
    get_canonical_tropical_systems,
    get_native_alerts_for_point,
    get_reusable_alerts_for_country,
    get_swic_extreme_alerts,
    get_tropical_products,
    get_tropical_systems,
    get_tropical_systems_near,
    group_tropical_systems,
    match_alerts_to_point,
    match_tropical_systems_to_point,
)
```

The main entry point is:

- `get_alerts_for_point(lat, lon, country_code, lang=None, debug=False, active_only=False, progress=None)`

Other useful features:

- `get_swic_extreme_alerts(active_only=True, include_marine=False, debug=False)`
- `get_tropical_systems(source_ids=None, debug=False)` and `match_tropical_systems_to_point(systems, lat=..., lon=..., radius_km=1000.0)` for cache-friendly tropical fetching and local proximity matching
- `get_canonical_tropical_systems(source_ids=None, debug=False)` groups current observations only when their non-empty names match after trimming and case-insensitive comparison; `group_tropical_systems(systems)` applies the same local grouping to already-fetched reports
- `get_tropical_products(system, debug=False)` lazily retrieves optional source-specific detail only after a caller selects one `TropicalSystem`; ordinary discovery never performs these follow-up requests
- `get_tropical_systems_near(lat, lon, radius_km=1000.0, source_ids=None, debug=False, progress=None)`
- cache-safe reusable/native alert queries with `get_reusable_alerts_for_country()`, `get_native_alerts_for_point()`, `match_alerts_to_point()`, and `deduplicate_alerts()`

Notes:

- the caller supplies the correct ISO country or territory `country_code`; the library does not infer location from coordinates. A source can cover additional territory codes—for example, NWS routes `US`, `AS`, `GU`, `MP`, `PR`, and `VI` to its native point API.
- if a country has multiple language-specific feeds, English-capable sources are preferred by default
- if you request an unsupported language tag, the library warns and falls back to the default source selection
- `get_alerts_for_point(...)` raises `UnsupportedCountryError` when no alert sources are registered for the supplied country
- returned `Alert` and `TropicalSystem` objects include optional `source_info` metadata when produced through the public query helpers
- tropical-system sources are not currently routed through `country_code` point queries
- applications may cache raw results from `get_tropical_systems()` briefly by source, then call `match_tropical_systems_to_point()` for every selected location; keep this cache separate from ordinary warning candidates
- tropical `source_info.issuer_country_code` is an optional ISO code for the issuing centre's operational location; use it only to rank already-matched systems for presentation, never to filter regional systems
- tropical `system.display_geography` resolves source-and-basin hints first, then a source-wide hint, then an issuer-country default; source metadata stays declarative and never changes `issuer_country_code`
- current explicit map-context exceptions are CPHC → Hawaii and Météo-France La Réunion → Réunion; NHC Eastern Pacific observations use the ordinary US issuer-country context
- each `CanonicalTropicalSystem` contains only a normalized display `name` and ordered source `observations`; it has no canonical centre, track, wind, pressure, movement, classification, or intensity
- tropical systems retain source-specific tracks, cones, wind fields and warning layers only when the official structured product supplies those coordinates. Explicit ordered analysed or forecast positions may form a track, but the library does not buffer points, project radii, join probability circles, geocode prose, or otherwise manufacture area geometry. Scalar radii, axes, distances and provider-stated probabilities remain source facts in `parameters` or lazy structured products
- CMA supplies analysed and BABJ forecast tracks, JMA supplies forecast-centre tracks when the latest VPTW report contains them, and HKO forecast tracks contain only timed/indexed fixes rather than untimed display-curve vertices. A track, probability area, cone, wind field, watch, or warning keeps its provider meaning and is not automatically a local official warning
- supplementary `TropicalProduct` objects keep a small semantic `kind`, the provider's natural `label`, Markdown-formatted text by default, and optional provider-specific structured `data`; providers may retain `plain` for layouts that render poorly as Markdown. Product sets intentionally vary by provider and may be empty

After selecting a source observation, retrieve richer detail explicitly:

```python
systems = get_canonical_tropical_systems(source_ids=["cphc_gis_central_pacific"])
observation = systems[0].observations[0]
products = get_tropical_products(observation)
```

NHC and CPHC currently expose matching wallet Public Advisory, Forecast
Discussion, Wind Probabilities, Warnings, and Update products when present.
Wallet contents are checked against the observation's ATCF identifier so a
stale product from a previously assigned wallet is not returned. Recognized
Public Advisory and Forecast Discussion layouts are conservatively formatted
as Markdown, including headings and fixed-width data blocks. Wind Probabilities
and Update products remain faithful plain text; Warnings use Markdown code
blocks. Unrecognized advisory layouts and PAGASA bulletin text receive only
safe escaping and preserved line breaks. PAGASA exposes its authoritative
Tropical Cyclone Bulletin as one product. JMA, CMA,
HKO, and Météo-France La Réunion expose useful structured forecast or analysis
detail from their existing official data. JMA's detail retains its native
analysis validity and additive current facts, plus concise forecast
classification, location, movement, pressure, wind and gust fields. Alternate
official units and meaningful conditions remain available as restrained JMA
source values. Probability-circle and wind/storm-warning thresholds, radii and
axes remain structured provider data rather than generated area geometry. A
provider with no reliable extra product simply returns an empty list. CMA's
lazy detail similarly retains its native thresholded quadrant radii and BABJ
forecast points without constructing wind polygons.

### Global WMO SWIC Extreme-warning discovery

For a global discovery view—such as a “show me an interesting warning now”
feature—use the explicit SWIC helper:

```python
from wevva_warnings import get_swic_extreme_alerts

alerts = get_swic_extreme_alerts()
```

It returns normal `Alert` objects for WMO SWIC map features classified as
`Extreme`, grouped by their mirrored CAP URL and with map geometry attached.
It defaults to locally active, non-marine candidates; pass
`include_marine=True` to include marine rows, or `active_only=False` to inspect
the complete WFS response. It is a discovery feed, not a replacement for
country point queries: its coverage is limited to warnings SWIC maps from
participating providers. `wevva` should rank or randomly select from the
returned list rather than treating its order as a severity ranking.

### Reusable country candidates and native point sources

Applications that need to match the same country's warnings to several points
can fetch candidates once and keep them according to their own cache policy:

```python
candidates = get_alerts_for_country("DE", lang="en")
berlin = match_alerts_to_point(candidates, lat=52.52, lon=13.405)
munich = match_alerts_to_point(candidates, lat=48.137, lon=11.575)
```

`get_alerts_for_country()` retains its original broad country-feed behaviour,
including sources that use native point queries. Do not cache its results as
local geometry candidates when a country has such a source.

For a cache that is safe across locations, use the split helpers instead:

```python
from wevva_warnings import (
    deduplicate_alerts,
    get_native_alerts_for_point,
    get_reusable_alerts_for_country,
    match_alerts_to_point,
)

# Cache by country/language; these are fetched only from non-native backends.
candidates = get_reusable_alerts_for_country("US", lang="en")

# On every location change, match the cache and fetch only native sources.
local = match_alerts_to_point(candidates, lat=40.71, lon=-74.00, active_only=True)
native = get_native_alerts_for_point(40.71, -74.00, "US", lang="en", active_only=True)
alerts = deduplicate_alerts([*local, *native])
```

Some country feeds arrive with administrative area codes but no CAP polygon.
Where a backend has a documented source-side geometry backfill, it is applied
while fetching these reusable candidates; later local matching and caching do
not make a boundary request.

The split is driven by each backend's `uses_native_point_query` capability;
no provider or country is special-cased. `get_reusable_alerts_for_country()`
does not fetch native sources, while `get_native_alerts_for_point()` does not
fetch reusable sources. Matching makes no network calls and may populate
missing supported geometry on supplied `Alert` objects from packaged geocode
data. Cache candidates without `active_only` if they will be matched at
different times, then apply `active_only=True` during local matching and the
native request.

### Point-query progress

Pass an optional `progress` callback to receive structured updates while a
point query runs. The callback is invoked synchronously on the calling thread;
UI callers running the query in a worker should marshal updates to their UI as
needed. Callback exceptions are ignored so a progress display cannot interrupt
the warning query.

```python
def show_progress(event: str, payload: dict[str, object]) -> None:
    if event == "source_started":
        print(f"Checking weather warnings from {payload['provider_name']}…")
    elif event == "alerts_checked":
        print(f"Checked {payload['completed']} of {payload['total']} warnings")


alerts = get_alerts_for_point(60.17, 24.94, "FI", progress=show_progress)
```

`WarningQueryProgress` is the public callback type. The stable events are
documented in [docs/architecture.md](docs/architecture.md).

### Tropical proximity progress

`get_tropical_systems_near(..., progress=callback)` uses the same synchronous,
exception-safe callback type, with its own event names. It first emits
`tropical_fetch_started` and source-level fetch events, then—after every
selected source with an available backend has returned—emits one exact
`tropical_check_total` followed by one `tropical_checked` event per returned
system and `tropical_finished`.
This lets a UI show an indeterminate fetch stage followed by a determinate
local proximity-check count without treating tropical systems as ordinary
country-routed warnings.

## CLI

Main commands:

- `wevva-warnings point LAT LON COUNTRY_CODE`
- `wevva-warnings country COUNTRY_CODE`
- `wevva-warnings source SOURCE_ID`
- `wevva-warnings tropical-groups`
- `wevva-warnings tropical-source SOURCE_ID`
- `wevva-warnings tropical-near LAT LON`
- `wevva-warnings tropical-products SOURCE_ID SYSTEM_ID`
- `wevva-warnings sources`

Useful flags:

- `--lang de`
- `--active`
- `--formatted` for table output on `country`, `source`, `tropical-source`, and `tropical-near`
- `--radius-km 1000` on `tropical-near`
- `--source SOURCE_ID` on `tropical-near` to restrict checked tropical-system sources
- `--source SOURCE_ID` on `tropical-groups` to restrict grouped source observations
- `--content` on `tropical-products` to inspect complete text and structured data
- `--kind tropical_system` on `sources` to list only tropical-system sources
- `--debug` on query commands to show fetch and matching progress

## Source registry

There are currently **175** registered sources in the built-in registry:
**166** alert sources and **9** tropical-system sources. Tropical-system
coverage includes the NHC/CPHC, JMA, CMA/NMC, HKO and PAGASA Northwest Pacific
products; BoM's Australian-region track products; and Météo-France La
Réunion's Southwest Indian Ocean RSMC data. Use the separate tropical queries
because these are not country-routed warning feeds.

This is the maintained compact tropical capability table. Geometry and lazy
products are optional and appear only when the current official product
contains them.

| Source ID | Issuer / region | Named geometry | Lazy products | Display geography |
| --- | --- | --- | --- | --- |
| `nhc_gis_atlantic` | NHC / Atlantic | `forecast_track`, `cone`, `watch_warning` | Public Advisory, Forecast Discussion, Wind Probabilities, Warnings, Update | default `US` |
| `nhc_gis_eastern_pacific` | NHC / Eastern Pacific | `forecast_track`, `cone`, `watch_warning` | Public Advisory, Forecast Discussion, Wind Probabilities, Warnings, Update | default `US` |
| `cphc_gis_central_pacific` | CPHC / Central Pacific | `forecast_track`, `cone`, `watch_warning` | Public Advisory, Forecast Discussion, Wind Probabilities, Warnings, Update | explicit Hawaii (`US-HI`) |
| `jma_tropical` | JMA / Northwest Pacific | `forecast_track` | Forecast | default `JP` |
| `cma_tropical` | CMA/NMC / Northwest Pacific and South China Sea | `observed_track`, `forecast_track` | Analysis, Forecast | default `CN` |
| `pagasa_tropical` | PAGASA / Philippine Area of Responsibility | none | Tropical Cyclone Bulletin | default `PH` |
| `bom_tropical` | BoM / Australian region | `forecast_track`, `warning_area`, `watch_area`, `forecast_area`, `wind_area` | none | default `AU` |
| `hko_tropical` | HKO / Northwest Pacific and South China Sea | `observed_track`, `forecast_track` | Forecast | default `HK` |
| `meteofrance_reunion_tropical` | Météo-France / Southwest Indian Ocean | `track` | Analysis, Forecast | explicit Réunion (`RE`) |

HKO's public map documents a 70% Potential Track Area, but neither its track
XML nor its separately published CSDI point GML supplies that area as geometry.
The library therefore does not copy the map's radius table or construct a cone
or potential-track polygon from HKO's forecast fixes.

India's documented IMD cyclone track, wind-warning, and cone APIs require
authenticated key access, so they are not registered built-in sources. WMO
SWIC's anonymous tropical JSON has also been evaluated but is not registered:
its issuing-centre separation and reuse terms are promising, while an RSMC New
Delhi example, identity across successive updates, and an observed quiet-state
response still need live validation. The library does not substitute the SWIC
aggregator for its direct tropical providers.

Known tropical follow-up work is recorded rather than hidden in provider
comments:

- [task 0004](docs/tasks/0004-explain-tropical-proximity-matches.md): expose why a tropical proximity query matched
- [task 0005](docs/tasks/0005-enrich-nhc-cphc-tropical-gis-layers.md): validate and normalize NHC wind-field geometry
- [task 0012](docs/tasks/0012-operationalise-tropical-systems-in-wevva.md): consume grouping, geography, and products in `wevva`
- [task 0013](docs/tasks/0013-validate-tropical-source-follow-ups.md): validate seasonal provider layouts during live events
- [task 0014](docs/tasks/0014-add-bmkg-tcwc-jakarta-tropical-source.md): implement the verified BMKG candidate
- [task 0017](docs/tasks/0017-finish-tropical-display-scope-and-geometry-semantics.md): resolve NHC Eastern Pacific map scope and remaining track semantics
- [task 0018](docs/tasks/0018-complete-structured-tropical-provider-data.md): preserve additional official tropical data without constructing geometry

For the full current list, use:

```bash
wevva-warnings sources
```

The source definitions themselves live in [wevva_warnings/sources.py](wevva_warnings/sources.py).

## Geocode Data

Some point queries resolve administrative geocodes to packaged boundary
artifacts when a provider does not supply a CAP polygon.

- `scripts/build_emma_geocodes.py` builds a packaged EMMA geometry dataset
- `scripts/build_emma_aliases.py` builds a packaged EMMA alias dataset
- `scripts/build_bom_amoc_geocodes.py` builds a packaged Australian BoM AMOC geometry dataset
- `scripts/build_jma_area_geocodes.py` builds a packaged JMA area-code geometry dataset

Currently supported at runtime:

- Meteoalarm `EMMA_ID` geometry resolution
- Meteoalarm alias resolution to EMMA geometry, including `NUTS2`, `NUTS3`, `WARNCELL`, `WARNCELLID`, `FIPS` and `CISORP`
- Australian BoM `AMOC-AreaCode` geometry resolution for polygonal `MW`, `RC`, `ME` and `PW` code families
- JMA `JMA Area Code` geometry resolution from official JMA GIS boundary datasets
- NWS geometryless-alert enrichment from official forecast, county, fire, and marine URLs in `affectedZones`

The runtime package ships only small derived artifacts under
`wevva_warnings/data/`. Large upstream source files are build inputs, not
packaged assets. Geometry is loaded lazily from packaged per-code artifacts;
EMMA aliases are shipped as a small plain JSON mapping.

Note that the EMMA geocode-polygon mapping is retrieved directly, but the aliases file is a Google Drive link which requires manual download. Both files are derived from the [`Meteoalarm Redistribution Hub`](https://meteoalarm.org/en/live/page/redistribution-hub#list).

The current Australian BoM path is narrower and uses official static BoM spatial
shapefiles behind `AMOC-AreaCode`, with the first cut focused on polygonal
`MW`, `RC`, `ME` and `PW` code families.

For sources using the `swic_mirror` backend, a geometry-less CAP alert can also
receive its matching WMO SWIC map polygon during fetch. This is a bounded,
best-effort source enrichment: CAP geometry and packaged geocode geometry take
precedence, and an unavailable WFS response leaves the raw alert unchanged.

NWS applies a similar bounded, best-effort enrichment during its native API
fetch. It keeps `properties.geocode` on `Alert.geocodes`, keeps the raw
`affectedZones` URL list in `Alert.parameters`, and consults only supported
`api.weather.gov` zone URLs when the alert has no explicit geometry. Shared
zone requests are deduplicated and successful boundaries are cached; partial
or complete zone failures do not discard the alert. The fallback never turns
an area description or other prose into geometry.

Intended pattern:

- keep raw provider geocodes on `Alert`
- normalize to one canonical geometry key if aliases are used
- ship only small derived boundary artifacts
- avoid runtime dependence on authenticated or mutable upstream APIs

## Source coverage follow-ups

The registry has a few coverage and reliability follow-ups in four useful
categories.

### Quiet feeds

The following feeds were reachable but had no current alerts when checked on
2026-08-11. This is not a coverage failure; a future live event is needed to
exercise their full retrieval path.

| Source ID | Provider | Checked | Note |
| --- | --- | --- | --- |
| `vedur` | Icelandic Meteorological Office | 2026-08-11 | RSS feed was empty |
| `dma_anguilla` | Disaster Management Anguilla | 2026-08-11 | Atom feed was empty |
| `antigua_met` | Antigua and Barbuda Meteorological Service | 2026-08-11 | Atom feed was empty |
| `dem_barbados` | Department of Emergency Management Barbados | 2026-08-11 | Atom feed was empty |
| `dmh_myanmar` | Department of Meteorology and Hydrology Myanmar | 2026-08-11 | Atom feed was empty |
| `meteo_cw_en` | Meteorological Department Curaçao | 2026-08-11 | English feed was empty |

### Operational follow-ups

These feeds are live, but deserve separate performance or endpoint-resilience
work rather than being treated as missing coverage:

| Source ID | Provider | Checked | Note |
| --- | --- | --- | --- |
| `ametvigilance_dz` | AmetVigilance Algeria | 2026-08-11 | Live, high-volume feed; review performance and product selection |
| `saudi_ncm_en`, `saudi_ncm_ar` | Saudi NCM | 2026-08-11 | Live, high-volume feeds; English endpoint was notably slow |
| `svg_met` | Saint Vincent and the Grenadines Meteorological Services | 2026-08-11 | Primary CAPEWS endpoint timed out while checking |

### Recently added or restored endpoints

PAGASA and the Thai Meteorological Department are currently live. Their focused
backends support PAGASA's `application/cap+xml` `.cap` documents and TMD's
current `/uploads/CAP/` document paths, while retaining their legacy URL forms.

South Africa is supported through official SAWS alerts mirrored by WMO SWIC.
Its focused backend uses feed expiry metadata to avoid fetching the mirror's
long history, and preserves separately timed English `info` blocks and their
polygons as distinct alerts.

Colombia's official IDEAM alerts are consumed through WMO SWIC's HTTPS mirror.
The focused backend filters the mirror history before fetching linked CAP
documents, which cover meteorological, hydrological, landslide, and forest-fire
alerts and provide detailed polygons suitable for local point matching.

India combines three official structured routes under the existing
`imd_india` source: the WMO Alert Hub IMD CAP mirror, CAP alerts relayed by
NDMA SACHET, and warning-coloured IMD district nowcasts from its public WFS.
SACHET entries must be meteorological and carry direct IMD sender provenance
or an IMD CAP reference; CWC and unrelated state/all-hazards alerts are not
included. CAP text and LGD geocodes are preserved, linked SACHET XML uses ETag
caching, and the WFS nowcasts provide official district geometry for local
matching. A headline is generated from structured nowcast fields only when IMD
publishes no message; generated text is marked in `Alert.parameters` and is
never presented as an IMD description or instruction.

Syria is supported through the Ministry of Emergency and Disaster Management's
official Arabic CAP feed. It publishes public all-hazard warnings with native
polygons, including weather, flood, marine, and other emergency alerts.

Uganda is supported through the Department of Meteorological Services' public
WIDS Atom feed. The feed contains active alerts only; linked CAP documents
provide English, Swahili, and Luganda text, native polygons, and geocodes.

Somalia is supported through the Somalia National Meteorological Agency's
public CAP RSS feed. Its linked English CAP documents provide explicit expiry
times and native polygons suitable for local point matching.

Niger is supported through the Direction de la Météorologie Nationale's public
French CAP RSS feed. Its linked documents provide explicit expiry times and
native polygons; the endpoint was healthy but its newest alert was from June
2024 when checked in October 2026.

Sudan also has an English hydrological source from the General Administration
of Nile Waters Affairs. Its public CAP feed supplies explicit expiry times and
separate native polygons for affected Blue Nile and White Nile reaches.

Mali is supported through MALI-METEO's public French CAP RSS feed. Its current
storm and rainfall alerts provide explicit expiry times and native polygons for
local point matching.


### Intentionally skipped language variants

These are additional language feeds or mirror variants for countries already in
the registry. We skipped them deliberately rather than because they were missed.

| Country / provider | Missing variant | Current support | Note |
| --- | --- | --- | --- |
| Cameroon | `cm-meteo-ha` | `meteo_cameroon_en`, `meteo_cameroon_fr` | Hausa mirror feed not enabled |
| Curaçao and Sint Maarten | `cw-meteo-es` | `meteo_cw_en`, `meteo_cw_nl`, `meteo_cw_pap` | Spanish WMO mirror not enabled |
| Mongolia | `mn-namem-mn` | `namem_en` | Mongolian feed not enabled |
| Nigeria | `ng-nimet-ha` | `nimet_en` | Hausa feed not enabled |
