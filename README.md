# wevva-warnings

`wevva-warnings` is a small Python library and CLI for looking up official weather warnings for a single point.

It pulls from official CAP feeds and national meteorological APIs, normalizes the results into a compact `Alert` model, and filters them to the coordinates you asked about.

The project is intentionally narrow:

* you supply `lat`, `lon`, and a `country_code`
* the registry picks the right official source or sources for that country
* alerts are matched by native point query or by geometry
* the output stays close to what the provider actually published

It is not trying to infer countries from coordinates, invent a cross-provider severity model, or aggressively merge alerts that happen to look similar.

## Install

```bash
pip install wevva-warnings
```

## Quick start

### Python

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
    print(alert.severity)
    print(alert.url)
```

If a country publishes multiple language-specific feeds, you can steer source selection with `lang`:

```python
german_alerts = get_alerts_for_point(
    lat=49.8,
    lon=7.67,
    country_code="DE",
    lang="de",
)
```

### Command line

The CLI has three commands: `point` for coordinate lookups, `source` for inspecting one registered source, and `sources` for the built-in registry.

```bash
wevva-warnings point 40.71 -74.00 US
```

If you want a particular source language when a country has multiple feeds:

```bash
wevva-warnings point 49.8 7.67 DE --lang de
```

If you only want alerts that are active right now:

```bash
wevva-warnings point 28.12 -17.24 ES --active
```

If you want progress output while a query is running:

```bash
wevva-warnings point 40.71 -74.00 US --debug
```

To inspect the built-in source registry:

```bash
wevva-warnings sources
```

To fetch alerts from one specific source:

```bash
wevva-warnings source fmi_en
```

By default, `source` pretty-prints compact `Alert` objects. To render one
source as a table instead:

```bash
wevva-warnings source fmi_en --formatted
```

You can also run the CLI as a module:

```bash
python -m wevva_warnings point 40.71 -74.00 US
```

Human CLI output is deliberately compact and readable: headline, event, severity, times, and description. If you need structured output, use the Python API.

## What You Get

* Normalized `Alert` model, including source alert URLs when available
* Point-based warning queries
* CAP parsing
* Polygon, MultiPolygon, and CAP circle matching
* Official API backends for NWS and GeoMet
* Dedicated provider backends for AEMET, ANMETEO, Bahrain Meteorological Directorate, Belgidromet, Belize National Meteorological Service, BMKG, BoM and CMA via the WMO SWIC mirror, Botswana Department of Meteorological Services, CAPEWS Caribbean feeds, Cameroon National Meteorology, Chad, Comoros, Congo, Curaçao Meteorological Department, Djibouti, DMH Myanmar, DMH Paraguay, DR Congo, DWD, Ecuador INAMHI, Ethiomet, FMI, Ghana Meteorological Agency, Hong Kong Observatory, HydroMet Guyana, Hydrometcenter, IGBU, Icelandic Meteorological Office, India Meteorological Department, INAM Mozambique, INDOMET, INMET Brazil, INMET Guinea-Bissau, INUMET, Jordan Meteorological Department, KMA, Kazhydromet, Kyrgyzhydromet, Kenya Meteorological Department, Maldives Meteorological Service, MET Norway, METEO-BENIN, Meteorological Service of Jamaica, Met Eireann, MetService New Zealand, MeteoBurkina, MeteoChile, MeteoGambia, MeteoLiberia, MeteoMauritanie, MetMalawi, MeteoSC, MeteoSouthSudan, MeteoSudan, MeteoTogo, Mexico SMN, NAMEM Mongolia, Nigerian Meteorological Agency, NVE, PAGASA, Qatar Civil Aviation Authority, Saint Lucia, SLMET, SMG, SMN, Solomon Islands Meteorological Service, TCI Emergency Alerts, Thai Meteorological Department, TMA, Trinidad and Tobago Meteorological Service, Uzhydromet, Vanuatu Meteorology and Geo-Hazards Department, WeatherZW, and ZMD
* Reusable generic CAP feed backend
* Dedicated Meteoalarm Atom backend for Meteoalarm feeds
* Static curated source registry

The `wevva-warnings sources` table includes a `V2` column marking sources that
have had the newer provider-specific parsing pass.

## Public API

```python
from wevva_warnings import get_alerts_for_point, get_alerts_for_source, list_sources
```

`get_alerts_for_point(lat, lon, country_code, lang=None, debug=False, active_only=False)` is the primary API. It:

1. finds the matching source or sources for the supplied country code
2. optionally narrows source selection by language metadata
3. dispatches to the right backend
4. filters alerts by native point query or geometry
5. returns normalized `Alert` objects

`get_alerts_for_source(source_id, active_only=False)` is a lower-level helper for debugging or source-specific use.

`list_sources()` returns the built-in source registry as `WarningSource` objects.

`get_alerts_for_point(...)` raises:

* `UnsupportedCountryError` when no sources are registered for the supplied `country_code`

The caller is responsible for supplying the correct `country_code`. The library does not infer country from coordinates.

If a country has multiple language-specific feeds and you do not pass `lang`, the library prefers English-capable sources when available. Otherwise it uses the first declared source for that country. If you request a language that is not supported for that country, `get_alerts_for_point(...)` emits a warning and falls back to the default source selection.

## CLI summary

* `wevva-warnings point LAT LON COUNTRY_CODE`
* `wevva-warnings point LAT LON COUNTRY_CODE --lang de`
* `wevva-warnings point LAT LON COUNTRY_CODE --active`
* `wevva-warnings point LAT LON COUNTRY_CODE --debug`
* `wevva-warnings source SOURCE_ID`
* `wevva-warnings source SOURCE_ID --active`
* `wevva-warnings source SOURCE_ID --formatted`
* `wevva-warnings source SOURCE_ID --debug`
* `wevva-warnings sources`

If you request an unsupported country code, the CLI exits with an error. If you request an unsupported language for a supported country, it warns and falls back to the default source selection.

## Source model

The package is built around two concepts:

* backends are ingestion strategies such as `nws`, `geomet`, `generic_cap`, `meteoalarm_atom`, and a small number of provider-specific backends where the source shape or behavior justifies it
* sources are static definitions that point at real official warning feeds or APIs for a given country code and language

Most CAP sources still go through shared ingestion paths, but providers with useful quirks or special behavior can have their own modules without changing the public API.

## Testing

Running an individual test module directly is useful while developing, for example:

```bash
uv run python tests/test_query.py
```

## Source registry

There are currently **151** enabled sources in the built-in registry.

Some provider backends have been migrated structurally, but could not be fully
validated against live alerts because the feed was empty when checked. These
should be revisited later:

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

For the full current list, use:

```bash
wevva-warnings sources
```

The source definitions themselves live in [wevva_warnings/sources.py](wevva_warnings/sources.py). The looser [all_sources.txt](all_sources.txt) file is kept as a broader reference and backlog.

## WMO Gap Tracker

The [sources.csv](sources.csv) file is a local snapshot of the WMO source list.
Compared with the current registry, the remaining gaps fall into four useful
categories.

### Genuinely new providers

At the moment there are no remaining clean WMO-mirror provider gaps in this
table. The remaining expansion work is mostly in the revisit-later queue,
language variants we skipped deliberately, or special cases like Australia and
China.

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

### Good next candidates

There are no remaining top-priority candidates in this bucket right now. The
main unfinished work is the revisit-later queue and the intentionally skipped
language variants.

## Notes

CAP feed entries are curated manually from authoritative official sources, including the WMO SWIC sources table as a maintainer reference.

BMKG requires downstream applications to credit BMKG as the data source when using its CAP feeds.

Meteoalarm support is registered broadly through the Atom backend, but the usefulness of individual country feeds still depends on the linked CAP alerts carrying point-matchable geometry.

Some CAP feeds, such as Bahrain, are published through the WMO Alert Hub mirror URLs listed in the SWIC catalogue rather than a provider-hosted domain.
