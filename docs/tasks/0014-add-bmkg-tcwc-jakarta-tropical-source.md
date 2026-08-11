# Task 0014: Add the BMKG / TCWC Jakarta tropical-system source

## Status

Ready for implementation

## Target repository

`../wevva-warnings`

## Context

BMKG operates Indonesia's Tropical Cyclone Warning Centre (TCWC Jakarta). Its
official tropical-cyclone site is a public application at
`https://tropicalcyclone.bmkg.go.id`. Unlike the India candidate, it exposes
the structured current-system data used by that application through its
anonymous public CMS; no PDF or image parsing is needed.

On 2026-08-11, the root page declared the CMS base URL as
`https://tropicalcyclone.bmkg.go.id/cms`. The page's public JavaScript requests
the `tc_id`, `tc_data`, `tc_production`, and `tc_outlook` collections. The
observed historical system records and point records demonstrate a coherent
machine-readable model spanning more than one event. The current outlook also
provides an explicit no-system state between events.

This is a complementary operational-centre perspective for Indonesia and its
TCWC area, rather than a replacement for the existing JMA, CMA/NMC, BoM, or
other tropical sources. Overlap is expected and must be retained as separate
source results; cross-source tropical-system deduplication remains a consumer
decision.

## Problem

The package has no tropical-system source for TCWC Jakarta despite an official,
public, structured service with the core facts needed for the small
at-a-glance `TropicalSystem` presentation. Omitting it leaves a useful
Indonesia/TCWC viewpoint unavailable, while treating its advisory PDFs or
graphics as the source would be needlessly brittle.

## Desired outcome

Add a focused `bmkg_tropical` source that returns each current tropical cyclone
published by TCWC Jakarta with its latest analysed centre and compact current
facts. It must return no systems when the service publishes none, must not
return historical records, and must not report tropical disturbances/seeds as
tropical cyclones unless the source explicitly marks them as such.

## Scope

- Add a `bmkg_tropical` `WarningSource` with `kind='tropical_system'`,
  `issuer_country_code='ID'`, `lang='id,en'`, and the official public site URL.
- Add a small dedicated backend and register it in both backend registries.
- Query the public CMS system collection, selecting only records where both
  `is_current` and `is_cyclone` are true.
- For each selected system, query its enabled analysis records and select the
  newest non-forecast observation. Preserve forecast data only if a compact
  existing `TropicalSystem` field or `parameters` key has a clear meaning.
- Normalize the current name, classification/category, ID/code, issue or
  analysis time, `track_point` centre, pressure, mean wind, gust (when
  supplied), and source URL. Keep native values and units explicit rather than
  guessing conversions or classifications.
- Preserve useful raw fields in `parameters`, including TCWC's code, area,
  responsibility indicator, category, analysis time, uncertainty, wind
  distance, and quadrants when present.
- Add deterministic fixtures for an active named cyclone, an active non-cyclone
  seed, an inactive historical system, multiple analysis/forecast points, and
  incomplete records.
- Update `README.md` and `docs/architecture.md` source counts, provider list,
  and coverage wording only after the source is registered.
- Add the source to the tropical registry tests, including its issuer country
  metadata.

## Non-goals

- Do not parse downloaded TCWC PDFs, bulletin graphics, map tiles, or HTML
  prose.
- Do not include `is_cyclone=false` tropical seeds/invests in this task.
- Do not derive local warning polygons, cones, or wind areas from `quadrants`.
- Do not change cross-source `TropicalSystem` deduplication or make the source
  exclusive for Indonesia.
- Do not add live-network tests or rely on an active cyclone existing when the
  work is run.
- Do not use the ordinary `bmkg_en`/`bmkg_id` CAP warning sources as a
  substitute: they remain separate country-routed alert sources.

## Relevant code

- `wevva_warnings/models.py`
- `wevva_warnings/query.py`
- `wevva_warnings/sources.py`
- `wevva_warnings/registry.py`
- `wevva_warnings/backends/base.py`
- `wevva_warnings/backends/cma_tropical.py`
- `wevva_warnings/backends/bom_tropical.py`
- `wevva_warnings/backends/__init__.py`
- `tests/test_cma_tropical.py`
- `tests/test_provider_backends.py`
- `tests/test_registry.py`
- `docs/tasks/0009-document-tropical-system-contract.md`
- `docs/tasks/0013-validate-tropical-source-follow-ups.md`

## Observed public data contract

The following unauthenticated requests were observed on 2026-08-11. They are
the public site's own requests, not a separately promised API, so keep the
adapter narrow and make failure return an empty result through the usual backend
handling.

1. System list:
   `GET https://tropicalcyclone.bmkg.go.id/cms/items/tc_id`

   Records include `id`, `name`, `tc_code`, `is_current`, `is_cyclone`,
   `is_aor`, `area`, `season`, and update timestamps. Use a server-side filter
   for current systems where supported, but apply the same boolean checks in
   Python so an unexpected CMS query response cannot admit historical systems.

2. Per-system points:
   `GET https://tropicalcyclone.bmkg.go.id/cms/items/tc_data`

   Filter by the system `tc_id` and enabled records. The public application
   distinguishes analysed (`is_forecast=false`) from forecast
   (`is_forecast=true`) points. Observed fields include a GeoJSON
   `track_point`, `time`, `pressure`, `mean_wind`, `gust`, `cat`,
   `wind_distance`, `uncertainty`, `analysis_time`, `is_enabled`, and wind
   `quadrants` (`ne`, `nw`, `se`, `sw`). `track_point.coordinates` are
   longitude, latitude.

3. Current outlook:
   `GET https://tropicalcyclone.bmkg.go.id/cms/items/tc_outlook`

   This was observed as a rendered no-cyclone outlook at 07:00 WIB on
   2026-08-11. It is contextual evidence but must not override the current
   system list or be parsed as the system source.

The historical record for Kujira (`tc_code='94W'`) demonstrated the list and
point relation, including a forecast record with a GeoJSON centre, pressure,
mean wind, category, analysis time, uncertainty, and quadrant fields. Capture
a minimal redacted fixture from this public response, plus an active-shaped
fixture, rather than fetching live data in tests.

## Approach

1. Read `docs/architecture.md` and the tropical-system contract task before
   editing public models, source registration, or routing.
2. Inspect `TropicalSystem` field meanings and mirror the narrow current-fact
   normalization used by the CMA and BoM adapters. Do not alter the public
   model solely for a BMKG-specific optional field.
3. Implement a backend that requests the system list, validates its response,
   filters current actual cyclones, then requests the enabled analysis points
   for each selected system.
4. Choose the newest usable non-forecast point by its valid/analysis timestamp.
   If no usable current analysis has a valid point, omit that system rather
   than emitting invented coordinates. Document any exception only if the
   public site proves a different lifecycle convention.
5. Map the compact output fields. Store native category and supplementary
   values in `parameters`; do not assume pressure/wind units without confirming
   them from the source's public labels or a representative active payload.
6. Write fixture tests before registration: current cyclone included; a current
   seed rejected; inactive cyclone rejected; newest analysis chosen over older
   and forecast points; malformed/missing point safely skipped; metadata and
   raw parameters preserved.
7. Register the source, update counts/docs/tests, run the full suite and build,
   and record final endpoint/units decisions in this task's outcome.

## Acceptance criteria

- `list_tropical_sources()` contains `bmkg_tropical` with Indonesian issuer
  metadata, and source-specific CLI retrieval works through the normal tropical
  query path.
- An active actual cyclone yields one `TropicalSystem` with a valid latest
  analysed centre, identification, classification when provided, and unmodified
  provider facts.
- A current tropical seed and an inactive historical cyclone both yield no
  `TropicalSystem`.
- Forecast-only points do not replace the latest analysis as the displayed
  centre.
- Missing/invalid optional values do not prevent another valid BMKG current
  system from being returned.
- Existing warning and tropical source behavior, language selection, progress,
  and deduplication remain compatible.
- All tests are fixture-based; no active event or live CMS access is required.

## Verification

```bash
uv run python -m unittest tests.test_bmkg_tropical -v
uv run python -m unittest discover -s tests -v
uv build
```

Before release, perform a read-only live check of the official site and report
whether the current list/outlook agrees with the adapter's zero-or-more result.
Do not make this live check part of automated tests.

## Decisions and notes

- This task is a go decision based on BMKG's official public application and
  structured CMS responses observed on 2026-08-11. The data route is public but
  not separately documented as a stable third-party API, so a bounded adapter,
  defensive response validation, and fixtures are important.
- `is_current` is the lifecycle boundary; `is_cyclone` prevents seeds/invests
  from being presented as named tropical systems. Retain both checks even if
  the server-side filter is used.
- The ordinary BMKG CAP sources already improve Indonesian weather-warning
  coverage. This source provides tropical-system situational information and
  should not be confused with a location-specific official warning.
- TCWC Jakarta data may overlap systems from JMA, CMA/NMC, and BoM. It is
  valuable because it is independently issued and can supply a timely regional
  view, but it must retain `source='bmkg_tropical'`.

## Outcome

Not started.
