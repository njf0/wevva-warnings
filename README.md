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
wevva-warnings point 28.12 -17.24 ES --active-only
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
wevva-warnings source fmi_cap_en
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
* Reusable generic CAP feed backend
* Dedicated Meteoalarm Atom backend for Meteoalarm feeds
* Static curated source registry

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
* `wevva-warnings point LAT LON COUNTRY_CODE --active-only`
* `wevva-warnings point LAT LON COUNTRY_CODE --debug`
* `wevva-warnings source SOURCE_ID`
* `wevva-warnings source SOURCE_ID --active-only`
* `wevva-warnings source SOURCE_ID --debug`
* `wevva-warnings sources`

If you request an unsupported country code, the CLI exits with an error. If you request an unsupported language for a supported country, it warns and falls back to the default source selection.

## Source model

The package is built around two concepts:

* backends are ingestion strategies such as `nws`, `geomet`, `generic_cap`, and `meteoalarm_atom`
* sources are static definitions that point at real official warning feeds or APIs for a given country code and language

This keeps the codebase small while making it easy to add future CAP-based sources through registry entries rather than new modules.

## Testing

Running an individual test module directly is useful while developing, for example:

```bash
uv run python tests/test_query.py
```

## Source registry

There are currently **89** enabled sources in the built-in registry.

For the full current list, use:

```bash
wevva-warnings sources
```

The source definitions themselves live in [wevva_warnings/sources.py](wevva_warnings/sources.py). The looser [all_sources.txt](all_sources.txt) file is kept as a broader reference and backlog.

## Unsupported sources

These entries are present in the [SWIC sources list](https://severeweather.wmo.int/sources.html) but are not currently enabled in the registry. Common reasons include feeds with no point-matchable geometry, stale or empty feeds, broken TLS, DNS or reachability problems, or sources that still need a proper verification pass.

* `A-C`: Afghanistan, Albania, Algeria, Angola, Anguilla, Antigua and Barbuda, Austria, Barbados, Belarus, Belgium, Bosnia and Herzegovina, Brazil, British Virgin Islands, Bulgaria, Central African Republic, China, Costa Rica, Côte d'Ivoire, Croatia, Cyprus, Czechia
* `D-M`: Denmark, Egypt, France, Gabon, Greece, Hong Kong, China, Hungary, Iran, Iraq, Ireland, Israel, Italy, Jamaica, Kuwait, Latvia, Lesotho, Libya (State of), Lithuania, Luxembourg, Madagascar, Mali, Malta, Mauritius, Mexico, Montenegro, Myanmar
* `N-S`: Netherlands, Niger, North Macedonia, Oman, Panama, Philippines, Poland, Portugal, Republic of Moldova, Romania, Saint Vincent and the Grenadines, São Tomé and Príncipe, Saudi Arabia, Senegal, Serbia, Singapore, Slovakia, South Africa, Suriname
* `T-Y`: Thailand, Timor-Leste, Tunisia, Tuvalu, Uganda, United Kingdom of Great Britain and Northern Ireland, Viet Nam, Yemen

## Partially supported entries

These countries are enabled, but not every feed or advertised language is currently registered:

* Cameroon: `en` and `fr` are supported; the `ha` feed is not enabled.
* Curaçao and Sint Maarten: Curaçao `en`, `nl`, and `pap` are supported; the WMO mirror `es` feed is not enabled, and Sint Maarten is not separately registered.
* India: the IMD `en` feed is supported; the NDMA `sachet` feed is not enabled.
* Mongolia: the `en` feed is supported; the `mn` feed is not enabled.
* Nigeria: the `en` feed is supported; the `ha` feed is not enabled.
* Republic of Korea: the `en` feed is supported; no separate verified `ko` feed is currently registered.
* Sudan: the source is enabled, but registered as `ar` because the live CAP payloads checked were Arabic-only despite the catalogue entry claiming English.
* Togo: the source is enabled, but registered as `fr` because the live CAP payloads checked were French-only despite the catalogue entry advertising `en, fr`.
* Ukraine: the Meteoalarm `en` feed is supported; no separate verified `uk` feed is currently registered.

## Notes

CAP feed entries are curated manually from authoritative official sources, including the WMO SWIC sources table as a maintainer reference.

BMKG requires downstream applications to credit BMKG as the data source when using its CAP feeds.

Meteoalarm support is currently limited to the subset of feeds whose linked CAP alerts contain point-matchable polygon geometry.

Some CAP feeds, such as Bahrain, are published through the WMO Alert Hub mirror URLs listed in the SWIC catalogue rather than a provider-hosted domain.
