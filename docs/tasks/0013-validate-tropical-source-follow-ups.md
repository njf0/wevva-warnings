# Task 0013: Validate tropical source follow-ups during live events

## Status

Partially completed

## Target repository

`../wevva-warnings`

## Context

The library now has working tropical-system adapters for NHC/CPHC, JMA,
CMA/NMC, PAGASA, BoM, HKO, and Météo-France La Réunion. They are fixture-tested
and selected live endpoints have been smoke-tested, but several useful products
are inherently seasonal or only appear for certain storm stages.

Fiji Meteorological Service remains a promising Southwest Pacific candidate.
Its current official track page was reachable but server-rendered no system
data while inactive; no stable active structured payload has yet been captured.
Météo-France Nouvelle-Calédonie is a separate local Southwest Pacific
candidate: its official cyclone page similarly gives an explicit no-phenomenon
state while inactive, and its active-system detail request has not yet been
captured. Neither is a registered source yet.
NHC also advertises a wind-field GIS asset whose link is retained but whose
format and threshold semantics are not yet normalized.

## Problem

Adding speculative parsers merely to increase nominal basin coverage would
reduce reliability. Conversely, leaving observations only in chat history
makes it hard to know when a source has enough evidence for a bounded backend
change.

## Desired outcome

Maintain an evidence-backed go/no-go record for deferred tropical source and
product candidates, and create deterministic fixtures only after a real
official payload validates their operational shape.

## Scope

- During relevant live events, check the registered source outputs against the
  issuer's public page/product and record parse gaps or confirmed behaviour.
- Capture small, redacted-as-needed structural fixtures from official HKO,
  Météo-France, NHC/CPHC, JMA, and BoM products when they exercise a path not
  already tested.
- For NHC, inspect one official wind-field asset and decide whether it can be
  represented as named thresholded geometry without conflating it with a
  watch/warning. If so, complete the remaining scope of task 0005.
- For Fiji and Météo-France Nouvelle-Calédonie, identify the actual
  active-system request/payload from each current official site, verify it
  survives more than one update, and make a clear go/no-go decision for each
  focused source. If one is not reliably obtainable, document the blocker and
  leave it unregistered.
- Evaluate other RSMC/TCWC candidates one at a time with the same standard;
  record a separate implementation task only after a go decision.

## Non-goals

- Do not add live-network tests.
- Do not scrape screenshots, interactive map pixels, social media, or an
  obsolete legacy endpoint.
- Do not claim worldwide tropical coverage or force a source to expose local
  warning geometry it does not publish.
- Do not add several providers opportunistically in one task.

## Relevant code

- `wevva_warnings/backends/nhc_gis.py`
- `wevva_warnings/backends/hko.py`
- `wevva_warnings/backends/meteofrance_reunion_tropical.py`
- `wevva_warnings/backends/jma_tropical.py`
- `wevva_warnings/backends/cma_tropical.py`
- `wevva_warnings/backends/pagasa_tropical.py`
- `wevva_warnings/backends/bom_tropical.py`
- `wevva_warnings/sources.py`
- `tests/test_provider_backends.py`
- `tests/test_hko_reunion_tropical.py`
- `docs/tasks/0005-enrich-nhc-cphc-tropical-gis-layers.md`

## Approach

1. Begin with the issuer's documented public endpoint, then inspect the exact
   request and structured response used by its current public page.
2. Record the source URL, observed update time, identifier, current centre,
   lifecycle signal, and all candidate impact/track fields before coding.
3. Reduce a representative payload to a deterministic fixture and write the
   parser test before adding a backend capability.
4. Test failed/missing optional products explicitly: a storm must still be
   returned from its core source when an enrichment is unavailable.
5. Update the source notes, this task outcome, and the relevant numbered
   implementation task in the same change.

## Acceptance criteria

- Each decision records sufficient official endpoint and field evidence for a
  new agent to reproduce the conclusion without rediscovering the source.
- New parsing is covered by deterministic fixtures and does not add a live
  test dependency.
- A missing optional enrichment cannot hide an otherwise valid current system.
- Fiji and Météo-France Nouvelle-Calédonie are each represented by a verified
  focused backend or have a clear, current documented no-go reason.
- NHC wind fields are either semantically represented with their threshold or
  explicitly left as source URLs.

## Verification

- Run focused provider tests and `uv run python -m unittest discover -s tests -v`.
- Run `uv build` if code or package documentation changes.
- Keep read-only live checks out of the test suite and report their date in
  the task outcome.

## Decisions and notes

- A quiet source during the off-season is normal; it is not evidence that the
  endpoint or parser is broken.
- Prefer deferral over a brittle source. The existing nine-source baseline is
  more useful than unverified nominal coverage.

## Outcome

On 2026-08-11, the China Meteorological Administration / National
Meteorological Center candidate was verified and implemented as
`cma_tropical`.

- The official NMC Typhoon Network's public list endpoint is
  `https://typhoon.nmc.cn/weatherservice/typhoon/jsons/list_default`; it
  returns JSONP entries with a lifecycle `start` or `stop` marker and a stable
  internal ID.
- Its corresponding `view_<internal-id>` endpoint supplies a current-analysis
  history with timestamp, classification code, centre, pressure, wind,
  direction, speed, current wind radii, and forecast-agency data.
- The focused adapter deliberately returns only `start` entries, chooses the
  newest observation, maps compact current facts, and preserves native code
  and wind-radii values. It does not infer warning geometry or make long
  tracks a new public surface.
- Fixture tests cover the JSONP wrapper, stopped-system exclusion, latest
  observation, Chinese fallback name, malformed detail, and source metadata.

On 2026-08-11, one further evidence-backed source was implemented.

- `pagasa_tropical` reads PAGASA's current Tropical Cyclone Bulletin page at
  `https://www.pagasa.dost.gov.ph/index.php/tropical-cyclone/severe-weather-bulletin/1`.
  It accepts an active rendered bulletin only and returns the named system,
  issue time, centre, wind, pressure, motion and wind extent when published.
  PAGASA explicitly renders a no-active-system message between events and
  keeps recent PDF bulletins as archive links; the adapter recognizes that
  state and never returns an archived storm as current.
- Deterministic tests cover active-vs-inactive selection, normalisation of all
  common current fields, source metadata, and the explicit archive guard.

The remaining task scope concerns NHC wind fields and two deliberately
deferred Southwest Pacific investigations. One further RSMC/TCWC review has
also produced a positive implementation decision:

- **BMKG / TCWC Jakarta:** the 2026-08-11 review found a genuine public,
  machine-readable current-system service behind BMKG's official tropical
  cyclone application. It exposes current/lifecycle flags, system IDs and
  names, analysed and forecast GeoJSON points, pressure, winds, category,
  analysis time, uncertainty, and quadrants. This is a positive go decision;
  implementation details and fixture requirements are recorded separately in
  `docs/tasks/0014-add-bmkg-tcwc-jakarta-tropical-source.md`.

- **Fiji Meteorological Service:** capture the active-system request and
  payload from the current official track site during an event, then verify
  that it remains stable across updates before designing a source.
- **Météo-France Nouvelle-Calédonie:** capture the active-system detail
  request behind `https://meteo.nc/fr/cyclone`; its inactive page currently
  exposes only a no-phenomenon state, so no parsing contract should be guessed.
