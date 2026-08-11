# Task 0003: Make the JMA tropical source return canonical current systems

## Status

Completed

## Target repository

`../wevva-warnings`

## Context

`jma_tropical` is the only current Northwest Pacific tropical-system source.
It reads JMA's broad `extra.xml` update feed and treats every entry whose text
mentions a typhoon, tropical depression, or ex-typhoon as a tropical-system
report.

That feed also carries national, regional, prefectural, marine, and
probability products which merely discuss a tropical cyclone. Several of those
products describe the same storm, use different event identifiers, and may
not include a centre. A live check on 2026-08-09 returned five separate
records concerning Typhoon 13 for a single Okinawa proximity query.

JMA's official product catalogue distinguishes dedicated tropical-cyclone
analysis/forecast and general-position products (`VPTI*` and `VPTW*`) from
the broader weather information products currently leaking into this source.

## Problem

The public API claims to return `TropicalSystem` values, but the JMA backend
currently returns a mixture of storm objects and local impact narratives. It
does not consolidate revisions, so consumers cannot safely use the result as a
storm list or deduplicate it by `(source, id)`.

## Desired outcome

Make `get_tropical_systems_for_source("jma_tropical")` return one current,
canonical `TropicalSystem` per JMA tropical cyclone, using the latest suitable
official report. Retain the original document URL and useful source fields,
but exclude local weather explanations that belong in the ordinary JMA alert
path.

## Scope

- Establish a small, documented allow-list of JMA tropical product families
  from the official catalogue. Include the product types needed for formation,
  position, and analysis/forecast information; do not select entries only by
  Japanese keyword presence.
- Extract the product code from the feed/document metadata before retrieving
  unnecessary documents where possible.
- Define a canonical JMA system identity. Prefer the official tropical-cyclone
  number when present; use a documented stable fallback only for a legitimate
  tropical product that lacks it.
- Collapse revisions and companion products to the newest usable report for
  each canonical system, using JMA's report time. Define deterministic
  tie-breaking so fixture results do not depend on feed order.
- Preserve `source_info`, the original source URL, JMA Event ID, information
  tag, headline, centre, movement, pressure, wind, and other useful raw
  parameters on the retained result.
- Add fixture coverage representing dedicated cyclone products, regional and
  prefectural false positives, multiple revisions, and a formation product.
- Update the source notes, README, and architecture document to explain
  exactly what JMA products are represented.

## Non-goals

- Do not translate Japanese headlines or summaries.
- Do not turn regional JMA weather narratives into additional
  `TropicalSystem` objects; ordinary alert sources remain responsible for
  location-specific warnings.
- Do not invent a cyclone number or infer one from coordinates or headline
  prose.
- Do not add a generic feed-routing framework or change NHC/CPHC parsing.
- Do not promise a universal `active_only` concept for tropical products in
  this task.

## Relevant code

- `wevva_warnings/backends/jma_tropical.py`
- `wevva_warnings/sources.py`
- `wevva_warnings/models.py`
- `wevva_warnings/query.py`
- `tests/test_provider_backends.py` and JMA fixtures
- `README.md` and `docs/architecture.md`

## Approach

1. Verify the exact JMA product codes and their intended content against the
   official catalogue and representative archived/current XML. Record the
   selected codes in a short backend-level comment or source note, rather than
   relying on an undocumented title convention.
2. Replace the broad marker-only entry filter with product-code selection.
   Keep a narrowly documented fallback only if it is needed for an official
   cyclone formation or position product.
3. Parse each selected report into an intermediate value containing canonical
   identity, report timestamp, product priority, and `TropicalSystem` fields.
   Select the newest value per identity after parsing.
4. Choose product priority deliberately when timestamps tie: a full
   analysis/forecast product should win over a less detailed companion product
   only where they represent the same JMA advisory.
5. Keep the public `TropicalSystem` shape and both existing tropical query
   functions unchanged. The corrected source inventory is a data-quality fix,
   not a new query API.

## Acceptance criteria

- A fixture containing one typhoon's analysis/forecast revisions returns one
  system with the most recent issued time and canonical cyclone identifier.
- Regional, prefectural, marine, and generic weather-information documents
  that mention that typhoon do not appear as systems.
- A legitimate developing-tropical-depression or formation product remains
  discoverable when it belongs to an allow-listed tropical family.
- Every returned JMA system has a meaningful source URL and preserves raw JMA
  identifiers in `parameters`.
- `get_tropical_systems_near()` no longer returns multiple JMA entries for
  one cyclone merely because several local offices discussed it.
- NHC/CPHC and existing public tropical APIs remain compatible.

## Verification

- Add deterministic XML fixtures for mixed product codes, duplicate revisions,
  and a new-system/formation case.
- Test canonical identity, newest-report selection, tie-breaking, metadata
  preservation, and proximity results with mocked requests.
- Retain the existing basic JMA parser fixture and extend it rather than using
  live JMA data as a test.
- Run `uv run python -m unittest discover -s tests -v`.

## Decisions and notes

- The implementation should prefer omission to misclassifying a local warning
  narrative as a storm object.
- The task intentionally improves the existing public result set; callers
  should not rely on historical duplicate or narrative records from the
  provisional backend.

## Outcome

Completed on 2026-08-11.

- The backend now selects only the JMA catalogue's dedicated `VPTI50`–`VPTI52`
  and `VPTW60`–`VPTW65` tropical products. It picks the newest Atom update for
  each product code before fetching, so local discussion products are never
  downloaded as prospective systems.
- Each report is parsed from its structured meteorological fields. JMA's
  `EventID` is its cross-product TC number, so it is the public ID; the later
  typhoon number is retained as source metadata. Report time followed by
  `VPTW` preference is the deterministic duplicate rule.
- The retained object preserves JMA product code, Event ID, information tag
  when present, typhoon number, source URL, centre, movement, pressure and
  wind. Fixture tests cover a stale revision, a lower-priority companion,
  excluded local narrative, and a numberless tropical-depression product.
- Follow-up metadata preservation completed on 2026-08-11: the public
  `advisory_number` now carries JMA's report serial, while `parameters`
  preserves the serial, publication type, analysis time, and native JMA class.
  This keeps useful at-a-glance source facts without expanding the common
  tropical model.
