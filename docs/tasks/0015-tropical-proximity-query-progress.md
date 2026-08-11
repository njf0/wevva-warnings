# Task 0015: Add progress to nearby tropical-system queries

## Status

Completed

## Target repository

`../wevva-warnings`

## Context

`get_tropical_systems_near()` queries every selected official tropical source,
then returns the systems whose current centre is within the caller's radius or
whose supplied polygon contains the point. Before this task, it returned only
when all that work was complete; unlike ordinary alert queries, it had no public
progress callback.

For a TUI, a small and truthful tropical-specific lifecycle is enough:

```text
Fetching tropical systems
        -> all selected providers have returned their systems
Checking tropical systems: 1 / N ... N / N
        -> nearby systems returned
```

This deliberately does not try to merge tropical systems into ordinary
country-routed warnings or construct one cross-product progress percentage.
They remain separate queries and separate result models.

Task 0006 proposed a broader tropical progress and source/basin-selection
project. This task completed the narrow `get_tropical_systems_near()` progress
slice needed by `wevva`; task 0006 retains only its broader unimplemented
work. The basin-selection work in 0006 was intentionally out of scope here.

## Problem

Without the callback, an application could not distinguish a slow tropical
source fetch from local proximity checking or show a determinate count of
returned systems as they were checked. It either left a progress indicator at
a misleading completed alert count or fell back to an uninformative spinner.

## Desired outcome

Add an optional, exception-safe progress callback to
`get_tropical_systems_near()` without changing its default return value or
matching behaviour. The callback must clearly divide source fetching from the
subsequent local check of every fetched `TropicalSystem`.

An application can therefore show an indeterminate “Fetching tropical
systems” stage, followed by one determinate “Checking tropical systems” bar.

## Scope

- Extend the existing public signature compatibly:

  ```python
  def get_tropical_systems_near(
      lat: float,
      lon: float,
      *,
      radius_km: float = 1000.0,
      source_ids: list[str] | None = None,
      debug: bool = False,
      progress: WarningQueryProgress | None = None,
  ) -> list[TropicalSystem]: ...
  ```

  Reuse `WarningQueryProgress` if its generic callback type remains suitable;
  tropical event names must nevertheless be distinct from alert-query events.

- Define and document this stable event vocabulary:

  | Event | Required payload | Meaning |
  | --- | --- | --- |
  | `tropical_fetch_started` | `lat`, `lon`, `source_total` | The proximity query has selected its sources with available backends. |
  | `tropical_source_started` | `source`, `provider_name` | One official tropical source is being fetched. |
  | `tropical_source_finished` | `source`, `candidates` | That source returned zero or more normalized systems. |
  | `tropical_check_total` | `total` | All selected sources have returned; the exact number of systems to test locally. |
  | `tropical_checked` | `completed`, `total`, `matched` | One system has been checked against the requested point/radius. `matched` is cumulative before `(source, id)` deduplication. |
  | `tropical_finished` | `system_count` | The final source/ID-deduplicated result list is ready. |

  `tropical_check_total` must be emitted exactly once, after all source fetches
  have finished. It must be followed only by `tropical_checked` and
  `tropical_finished`, never another fetch event. On a successful query path,
  every started source has one finished event. For zero fetched systems, emit
  `tropical_check_total(total=0)` and then `tropical_finished`.

- Fetch the selected sources first, retaining systems in deterministic source
  and provider-return order. Then perform the existing local proximity test
  once per fetched system, emitting one `tropical_checked` event per system.
  Preserve the current radius and polygon matching rule exactly.
- Preserve current `(source, id)` deduplication and result ordering semantics.
  It is acceptable for internal collection to contain duplicated source/ID
  values so long as each fetched candidate is counted/checkable and the final
  return preserves the current deduplicated result behaviour.
- Make callback exceptions non-fatal, consistent with ordinary alert query
  progress. Progress must not alter source selection, provider fetch requests,
  result order, matching, or error behaviour.
- Keep `source_ids` filtering and `debug` output compatible. The default
  remains all registered tropical sources.
- Update the public exports/type docs as necessary, README, and the tropical
  section of `docs/architecture.md`.

## Non-goals

- Do not add a combined alert-and-tropical context API, cross-product total,
  scheduler, cache, polling, async API, or threads.
- Do not change ordinary alert event names/payloads or route tropical sources
  by country.
- Do not make tropical systems ordinary `Alert` objects or infer official
  local warning status from proximity, a cone, or `issued_at`.
- Do not add a lifecycle/expiry filter, provider-specific active semantics, or
  cross-provider tropical merge.
- Do not require each backend to report the progress of its own linked assets;
  those requests truthfully belong to the fetching stage. The determinate
  total starts only when normalized systems are available to check.
- Do not implement the optional basin/source-selection additions proposed in
  task 0006 as part of this work.

## Relevant code

- `wevva_warnings/query.py`
- `wevva_warnings/progress.py` and `wevva_warnings/_debug.py`
- `wevva_warnings/__init__.py`
- `tests/test_query.py` and tropical backend/query tests
- `docs/architecture.md`, `README.md`, and task 0006

## Approach

1. Read the tropical-system architecture and task 0006, then settle one
   tropical event vocabulary before adding code.
2. Factor the current proximity loop only enough to collect normalized source
   systems during the fetch phase and perform the existing match/dedup pass
   afterwards. Keep provider backends and their HTTP behaviour unchanged.
3. Bind the optional callback around this helper using the existing
   exception-safe progress mechanism. Emit only the documented tropical events
   for this public call.
4. Add callback-recording tests with fake tropical sources/backends, including
   zero systems, multiple sources, duplicate source/ID values, a matched and
   unmatched system, filtered `source_ids`, and a callback that raises.
5. Update the docs and confirm no existing caller needs to pass `progress`.

## Acceptance criteria

- Calling `get_tropical_systems_near()` without `progress` returns exactly the
  same systems and preserves existing error/source-selection behaviour.
- With `progress`, events follow the documented two phases: all fetch events,
  exactly one check total, per-system checks with `completed` monotonically
  reaching `total`, then final completion.
- The check total equals the number of normalized systems actually checked,
  including `0`; it is not a provisional or source-count total.
- A callback exception does not change returned systems or interrupt another
  source.
- Existing source/ID deduplication, `source_ids`, radius matching, polygon
  containment, source metadata attachment, and `debug` behaviour remain
  compatible.
- `wevva` can map the events directly to “Fetching tropical systems” and
  “Checking tropical systems” without an artificial 100% pause.

## Verification

```bash
uv run python -m unittest tests.test_query -v
uv run python -m unittest discover -s tests -v
uv build
```

Use deterministic fake systems/backends only; do not make an active tropical
event or live provider request part of automated verification.

## Decisions and notes

- This is intentionally smaller than the combined context task it replaces.
  A tropical-only progress callback is reusable by any client and preserves
  the library's clean alert/tropical boundary.
- It permits a downstream UI to give tropical checks their own meaningful
  label and count. A genuinely combined alert-and-tropical percentage can be
  considered later only if a real product need remains after this simpler
  surface is exercised.

## Outcome

Implemented on 2026-08-11.

- `get_tropical_systems_near()` now accepts the backwards-compatible optional
  `progress` callback. It emits the documented tropical-only fetch lifecycle,
  then one exact local-check total and one check event per fetched candidate.
- Selected sources are first limited to available backends, so
  `tropical_fetch_started.source_total` is truthful. Each started source emits
  one finished event on the successful query path.
- The local check keeps provider/source order and the existing centre-or-polygon
  rule. Its cumulative `matched` count is pre-deduplication, while
  `tropical_finished.system_count` is the existing `(source, id)`-deduplicated
  result count.
- The query suppresses backend-level ordinary alert progress events while its
  tropical callback is active. Callback exceptions remain advisory.
- Fixture tests cover fetch/check event order, provider event isolation,
  duplicate candidates, source filtering, zero candidates, unavailable
  backends, and callback failure. Existing no-callback proximity behaviour is
  retained by its existing tests.
