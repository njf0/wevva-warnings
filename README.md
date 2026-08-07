# wevva-warnings

`wevva-warnings` is a small Python library and CLI for looking up official
weather warnings for a single point.

You provide `lat`, `lon`, and a `country_code`; the library picks the right
official source or sources, normalizes the returned alerts, and filters them by
native point query or geometry.

## Install

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

## Public API

```python
from wevva_warnings import (
    deduplicate_alerts,
    get_alert_sources_for_country,
    get_alerts_for_country,
    get_alerts_for_point,
    get_alerts_for_source,
    get_native_alerts_for_point,
    get_reusable_alerts_for_country,
    match_alerts_to_point,
    get_tropical_systems_for_source,
    get_tropical_systems_near,
    list_sources,
    WarningQueryProgress,
)
```

The main entry point is:

- `get_alerts_for_point(lat, lon, country_code, lang=None, debug=False, active_only=False, progress=None)`

Useful lower-level helpers:

- `get_alert_sources_for_country(country_code, lang=None)`
- `get_alerts_for_country(country_code, lang=None, active_only=False, progress=None)`
- `get_reusable_alerts_for_country(country_code, lang=None, active_only=False, progress=None)`
- `get_native_alerts_for_point(lat, lon, country_code, lang=None, debug=False, active_only=False, progress=None)`
- `match_alerts_to_point(alerts, lat, lon, active_only=False)`
- `deduplicate_alerts(alerts)`
- `get_alerts_for_source(source_id, active_only=False)`
- `get_tropical_systems_for_source(source_id)`
- `get_tropical_systems_near(lat, lon, radius_km=1000.0)`
- `list_sources()`

Notes:

- the caller supplies the correct `country_code`; the library does not infer country from coordinates
- if a country has multiple language-specific feeds, English-capable sources are preferred by default
- if you request an unsupported language, the library warns and falls back to the default source selection
- `get_alerts_for_point(...)` raises `UnsupportedCountryError` when no alert sources are registered for the supplied country
- returned `Alert` and `TropicalSystem` objects include optional `source_info` metadata when produced through the public query helpers
- tropical-system sources are not currently routed through `country_code` point queries

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

## CLI

Main commands:

- `wevva-warnings point LAT LON COUNTRY_CODE`
- `wevva-warnings country COUNTRY_CODE`
- `wevva-warnings source SOURCE_ID`
- `wevva-warnings tropical-source SOURCE_ID`
- `wevva-warnings tropical-near LAT LON`
- `wevva-warnings sources`

Useful flags:

- `--lang de`
- `--active`
- `--debug`
- `--formatted` for table output on `source` and `tropical-source`
- `--radius-km 1000` on `tropical-near`
- `--source SOURCE_ID` on `tropical-near` to restrict checked tropical-system sources
- `--kind tropical_system` on `sources` to list only tropical-system sources

## Source registry

There are currently **159** enabled sources in the built-in registry.
For the full current list, use:

```bash
wevva-warnings sources
```

The source definitions themselves live in [wevva_warnings/sources.py](wevva_warnings/sources.py).

## Geocode Data

Some EU point matching now uses packaged geocode boundary artifacts derived from
Meteoalarm source data.
- `scripts/build_emma_geocodes.py` builds a packaged EMMA geometry dataset
- `scripts/build_emma_aliases.py` builds a packaged EMMA alias dataset
- `scripts/build_bom_amoc_geocodes.py` builds a packaged Australian BoM AMOC geometry dataset
- `scripts/build_jma_area_geocodes.py` builds a packaged JMA area-code geometry dataset

Currently available at runtime:
- Meteoalarm `EMMA_ID` geometry resolution
- Meteoalarm alias resolution to EMMA geometry, including `NUTS2`, `NUTS3`, `WARNCELL`, `WARNCELLID`, `FIPS` and `CISORP`
- Australian BoM `AMOC-AreaCode` geometry resolution for polygonal `MW`, `RC`, `ME` and `PW` code families
- JMA `JMA Area Code` geometry resolution from official JMA GIS boundary datasets

The runtime package is intended to ship only the small derived artifacts under
`wevva_warnings/data/`. Large upstream source files are treated as build
inputs, not packaged assets. Geocode geometries now default to packaged
per-code artifacts for lazy loading at runtime, while EMMA aliases are shipped
as a small plain JSON mapping.

Note that the EMMA geocode-polygon mapping is retrieved directly, but the aliases file is a Google Drive link which requires manual download. Both files are derived from the [`Meteoalarm Redistribution Hub`](https://meteoalarm.org/en/live/page/redistribution-hub#list).

The current Australian BoM path is narrower and uses official static BoM spatial
shapefiles behind `AMOC-AreaCode`, with the first cut focused on polygonal
`MW`, `RC`, `ME` and `PW` code families.

Intended pattern:

- keep raw provider geocodes on `Alert`
- normalize to one canonical geometry key if aliases are used
- ship only small derived boundary artifacts
- avoid runtime dependence on authenticated or mutable upstream APIs

## Source Gap Tracker

The [sources.csv](sources.csv) file is a local snapshot of the WMO source list.
Compared with the current registry, the remaining gaps fall into four useful
categories.

### Empty feeds

Some provider backends have not been fully validated against live alerts because the feed was empty when checked. These should be revisited later:

| Source ID | Provider | Checked | Note |
| --- | --- | --- | --- |
| `nms_belize` | Belize National Meteorological Service | 2026-04-17 | RSS feed was empty |
| `meteo_cameroon_en` | Cameroon National Meteorology | 2026-04-17 | English feed was empty; French feed was live |
| `vedur` | Icelandic Meteorological Office | 2026-04-17 | RSS feed was empty |
| `qatar_caa_en` | Qatar Civil Aviation Authority | 2026-04-17 | RSS feed was empty |
| `qatar_caa_ar` | Qatar Civil Aviation Authority | 2026-04-17 | RSS feed was empty |
| `imd_india` | India Meteorological Department | 2026-04-17 | RSS feed was empty |
| `inam_mz` | INAM Mozambique | 2026-04-17 | RSS feed was empty |
| `eswatini_met` | Eswatini Meteorological Service | 2026-04-17 | RSS feed was empty |
| `msj` | Meteorological Service of Jamaica | 2026-04-17 | Atom feed had no active advisories |
| `dma_anguilla` | Disaster Management Anguilla | 2026-04-17 | Atom feed was empty |
| `antigua_met` | Antigua and Barbuda Meteorological Service | 2026-04-17 | Atom feed was empty |
| `dem_barbados` | Department of Emergency Management Barbados | 2026-04-17 | Atom feed was empty |
| `dmh_myanmar` | Department of Meteorology and Hydrology Myanmar | 2026-04-17 | Atom feed was empty |
| `meteo_cw_en` | Meteorological Department Curaçao | 2026-04-17 | English feed was empty |
| `meteoalarm_atom_andorra` | Meteoalarm | 2026-04-17 | Atom feed was empty |
| `pagasa` | PAGASA | 2026-04-17 | Atom feed was empty |
| `ametvigilance_dz` | AmetVigilance Algeria | 2026-04-17 | Candidate feed URL returned the web app shell, not a usable RSS or CAP feed |
| `kuwait_met` | Kuwait Meteorology | 2026-04-17 | Host did not resolve from this environment |
| `saudi_ncm_en` | Saudi NCM (English) | 2026-04-17 | Feed request hung or returned 503 while checking |
| `saudi_ncm_ar` | Saudi NCM (Arabic) | 2026-04-17 | Feed request hung while checking |
| `svg_met` | Saint Vincent and the Grenadines Meteorological Services | 2026-04-17 | Atom feed was empty |
| `tmd_en` | Thai Meteorological Department | 2026-04-17 | RSS feed was empty |
| `tmd_th` | Thai Meteorological Department | 2026-04-17 | RSS feed was empty |


### Intentionally skipped language variants

These are additional language feeds or mirror variants for countries already in
the registry. We skipped them deliberately rather than because they were missed.

| Country / provider | Missing variant | Current support | Note |
| --- | --- | --- | --- |
| Cameroon | `cm-meteo-ha` | `meteo_cameroon_en`, `meteo_cameroon_fr` | Hausa mirror feed not enabled |
| Curaçao and Sint Maarten | `cw-meteo-es` | `meteo_cw_en`, `meteo_cw_nl`, `meteo_cw_pap` | Spanish WMO mirror not enabled |
| India | NDMA `sachet` RSS | `imd_india` | Separate provider family from IMD |
| Mongolia | `mn-namem-mn` | `namem_en` | Mongolian feed not enabled |
| Nigeria | `ng-nimet-ha` | `nimet_en` | Hausa feed not enabled |
