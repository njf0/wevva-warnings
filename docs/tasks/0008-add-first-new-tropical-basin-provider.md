# Task 0008: Add the first validated tropical source outside current basins

## Status

Blocked by task 0007 decision

## Target repository

`../wevva-warnings`

## Context

The current tropical registry contains only NHC/CPHC and JMA sources. Task
0007 evaluates the preferred Australian-region candidate and records a
specific go/no-go decision. This task is the bounded implementation that
follows a go decision; it should not reopen source selection while coding.

## Problem

Tropical coverage currently omits the Australian region and much of the
Southern Hemisphere. A validated provider still needs an adapter, registry
entry, fixtures, public documentation, and honest geometry semantics before it
is useful to `wevva`.

## Desired outcome

Add one official, validated tropical-system source from task 0007 as a focused
backend that returns useful `TropicalSystem` values without weakening existing
source boundaries or claiming local warning coverage that the source does not
provide.

## Scope

- Implement exactly the source selected by task 0007. If its Outcome is
  no-go, do not start this task; create a new evaluation task for the next
  candidate instead.
- Add a stable `WarningSource` with truthful official URL, country/basin scope,
  language, notes, and `kind="tropical_system"`.
- Add one focused `WarningBackend`, register it, and keep provider-specific
  parsing rules in that backend.
- Populate stable ID, classification, name, headline, issued time, centre,
  movement, intensity, URLs, raw parameters, and named geometries only where
  the selected source actually provides them.
- Preserve revisions according to the selected source's documented update
  rules, returning one current object per storm where possible.
- Add mocked fixtures and update source-list, API, architecture, and tropical
  coverage documentation.

## Non-goals

- Do not add several regional providers in one change.
- Do not use a generic tropical-provider abstraction beyond `WarningBackend`.
- Do not infer land warnings from a track, cone, or centre.
- Do not convert the source into a country-routed `Alert` provider unless task
  0007 established a separate official alert product and a later task approves
  that work.
- Do not make live requests part of tests.

## Relevant code

- `wevva_warnings/sources.py`
- `wevva_warnings/registry.py`
- `wevva_warnings/backends/__init__.py`
- `wevva_warnings/backends/base.py`
- one new focused backend module
- `wevva_warnings/models.py` and `wevva_warnings/query.py`
- `tests/test_provider_backends.py`, `tests/test_registry.py`, and fixtures
- `README.md`, `docs/architecture.md`, and `TROPICAL_SYSTEMS.md`

## Approach

1. Carry the precise endpoint, archive/sample, product semantics, and revision
   rules from task 0007 into provider fixtures before writing the parser.
2. Implement a small adapter patterned after the closest current backend only
   where the upstream format genuinely matches. Do not copy NHC's GIS logic
   into a different provider without evidence.
3. Keep source-specific identifiers and raw values in `parameters` rather
   than flattening or fabricating a universal tropical taxonomy.
4. Add named geometry layers only after verifying their coordinate order and
   semantics. A provider with a centre only is still valid, but its limitation
   must be documented.
5. Verify source selection through `list_tropical_sources()`, direct source
   query, and the existing proximity flow.

## Acceptance criteria

- The new source is official, listed as `tropical_system`, and has a stable,
  documented source ID and endpoint.
- A fixture-backed direct query returns normalized systems with source metadata
  and accurate source-specific fields.
- The system appears in a proximity result only by the documented centre or
  polygon-layer rule.
- Revision handling returns the intended current system rather than every
  historical/update record in the source feed.
- Existing alert APIs and all existing tropical sources remain compatible.
- Documentation states basin coverage, language, and spatial limitations.

## Verification

- Add deterministic provider, registry, direct-query, and proximity-query
  tests using mocked payloads.
- Test malformed/empty optional data without discarding otherwise valid
  systems.
- Run `uv run python -m unittest discover -s tests -v` and `uv build`.

## Decisions and notes

- This is a template for one carefully chosen provider, not permission to add
  a succession of unvalidated sources.
- New basin work should continue as separate evaluate-then-implement pairs so
  source quality decisions remain reviewable.

## Outcome

Not started.
