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

## Public API

```python
from wevva_warnings import get_alerts_for_point, get_alerts_for_source, list_sources
```

The main entry point is:

- `get_alerts_for_point(lat, lon, country_code, lang=None, debug=False, active_only=False)`

Useful lower-level helpers:

- `get_alerts_for_source(source_id, active_only=False)`
- `list_sources()`

Notes:

- the caller supplies the correct `country_code`; the library does not infer country from coordinates
- if a country has multiple language-specific feeds, English-capable sources are preferred by default
- if you request an unsupported language, the library warns and falls back to the default source selection
- `get_alerts_for_point(...)` raises `UnsupportedCountryError` when no sources are registered for the supplied country

## CLI

Main commands:

- `wevva-warnings point LAT LON COUNTRY_CODE`
- `wevva-warnings source SOURCE_ID`
- `wevva-warnings sources`

Useful flags:

- `--lang de`
- `--active`
- `--debug`
- `--formatted` for table output on `source`

## Source registry

There are currently **151** enabled sources in the built-in registry.
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

Currently available at runtime:
- Meteoalarm `EMMA_ID` geometry resolution
- Meteoalarm alias resolution to EMMA geometry, including `NUTS2`, `NUTS3`, `WARNCELL`, `WARNCELLID`, `FIPS` and `CISORP`
- Australian BoM `AMOC-AreaCode` geometry resolution for polygonal `MW`, `RC`, `ME` and `PW` code families

The runtime package is intended to ship only the small derived artifacts under
`wevva_warnings/data/`. Large upstream source files are treated as build
inputs, not packaged assets.

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
