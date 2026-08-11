# Task 0011: Expose current WMO SWIC extreme-warning candidates

## Status

Complete

## Context

WMO's Severe Weather Information Centre (SWIC) publishes a global WFS map of
warnings that it can spatially represent. Its `s` property is the mapped
severity code; `s = 4` denotes an Extreme warning. The map is useful for a
consumer wanting to discover an interesting, currently active warning rather
than query a predetermined country or point.

## Problem

Country point queries cannot efficiently answer a global discovery question,
and a caller would otherwise need to know SWIC's WFS schema, retrieve many
map rows, group multiple polygon parts belonging to one CAP document, and
apply activity filtering itself.

## Desired outcome

Expose one small public Python API that returns normal `Alert` objects for
SWIC's mapped Extreme-warning candidates. It must be explicit about its WMO
SWIC coverage rather than claiming to be a complete worldwide warning search.

## Scope

- Add a global, registered WMO SWIC Extreme source and a focused WFS backend.
- Add `get_swic_extreme_alerts()` with local `active_only` filtering and an
  opt-in `include_marine` flag.
- Group WFS polygon rows by their exact `capurl`, preserving all polygon
  parts, area descriptions, timing, and concise WFS provenance.
- Return normal `Alert` objects with a link to the corresponding mirrored CAP
  document and `source_info` metadata.
- Add deterministic tests plus concise README and architecture documentation.

## Non-goals

- Do not add a global warning framework, a cache, a ranking algorithm, or a
  random-selection policy. `wevva` owns those presentation choices.
- Do not route this global source through country or point queries.
- Do not fetch every linked CAP document merely to improve WFS display text.
- Do not promise coverage beyond warnings SWIC maps from participating
  providers, or infer missing geometry.

## Relevant code

- `wevva_warnings/query.py`
- `wevva_warnings/__init__.py`
- `wevva_warnings/sources.py`
- `wevva_warnings/registry.py`
- `wevva_warnings/backends/`
- `tests/`
- `README.md`
- `docs/architecture.md`

## Approach

1. Query the WMO SWIC WFS for `s = 4`, adding `marine = '0'` unless the
   caller opts in to marine warnings.
2. Validate and group only polygonal map features by their exact relative CAP
   URL. Build one `Alert` per CAP URL, combining polygon parts into a
   `MultiPolygon` where necessary.
3. Map only safe, documented fields into `Alert`; preserve the WFS numeric
   codes and map-file name in `parameters` rather than guessing CAP labels.
4. Apply `Alert.is_active()` locally when requested. This avoids trusting WFS
   timestamp filtering and gives the new helper the established `active_only`
   meaning.
5. Keep request failure non-fatal and return no discovery candidates for that
   attempt, consistent with provider-query behaviour elsewhere in the
   library.

## Acceptance criteria

- The public function returns one normal `Alert` per exact WFS CAP URL.
- Multiple WFS polygon features are retained in a valid combined geometry.
- Default results exclude marine rows and default to currently active alerts;
  both choices are explicit and test-covered.
- The source is visible in the registry but never selected by country routing.
- Malformed/non-polygon WFS rows and WFS failures do not raise to consumers.
- Existing point, country, native, caching, language, and progress behaviour
  is unchanged.

## Verification

```bash
uv run python -m unittest discover -s tests -v
uv build
```

## Decisions and notes

- This is a discovery feed, not an authoritative replacement for national
  point queries. A returned CAP URL lets a consumer inspect the mirrored
  source document when it needs the original text.
- Activity is checked after retrieval because the WFS's timestamp fields are
  useful metadata but should not be relied on as the sole time filter.
- No progress callback is added: this one bounded request has no meaningful
  per-document work, and existing public progress event contracts remain
  untouched.

## Outcome

Implemented the explicit `get_swic_extreme_alerts()` public helper and a
registered global `swic_extreme` source backed by WMO SWIC WFS. The helper
returns one normal `Alert` per exact mirrored CAP URL, combines WFS polygon
parts, attaches source metadata, defaults to active non-marine candidates, and
retains an opt-in for marine and inactive records. Country routing, language
selection, cache helpers, and progress contracts remain unchanged.
