# Task 0009: Document the tropical-system public contract and `wevva` integration

## Status

Proposed

## Target repository

`../wevva-warnings`

## Context

Tropical-system support is intentionally separate from ordinary country-routed
weather alerts. It has different data sources, geography, languages, and
spatial concepts. The repository has an exploratory `TROPICAL_SYSTEMS.md`
note and terse API/CLI mentions, but no concise user-facing contract for a
consumer such as `wevva`.

Without that contract, a consumer can easily mistake a forecast cone for an
official warning, cache storm products incorrectly, or expect all tropical
basins and languages to be available.

## Problem

The public surface is discoverable but not yet sufficiently explicit about
coverage, geometry semantics, result freshness, source language, and the
division of responsibility between this library and the downstream TUI.

## Desired outcome

Provide concise, durable documentation that lets a consumer use tropical
system data safely alongside ordinary alerts, with no need to read backends or
the historical exploration note.

## Scope

- Add a README section for tropical systems, covering public APIs, CLI
  commands, current source/basin/language coverage, and a minimal `wevva`
  integration example.
- Document that tropical systems are not included in
  `get_alerts_for_point()` or country candidate caching, and must be queried
  separately.
- Explain the meaning and limitations of centre radius, forecast track,
  forecast cone, wind field, and official watch/warning layers. Incorporate
  task 0004's match-evidence API when available.
- State freshness/revision behaviour separately for each source where known;
  never equate `issued_at` with a universal expiry or active status.
- Update `docs/architecture.md` with the supported tropical query flow,
  progress contract from task 0006 if implemented, and source-boundary rules.
- Retain `TROPICAL_SYSTEMS.md` as a design/history note or replace it with a
  clear pointer to the maintained documentation; do not leave contradictory
  API proposals behind.

## Non-goals

- Do not promise global tropical coverage, automatic translation, or official
  local warnings for every returned system.
- Do not make documentation claim an unimplemented source, geometry layer, or
  API.
- Do not alter code behaviour solely to make an example look simpler.
- Do not duplicate volatile provider inventories in several files; choose one
  maintained source-coverage table and link to it elsewhere.

## Relevant code

- `README.md`
- `docs/architecture.md`
- `TROPICAL_SYSTEMS.md`
- `wevva_warnings/__init__.py`
- `wevva_warnings/cli.py`
- `wevva_warnings/models.py`
- `wevva_warnings/query.py`
- `wevva_warnings/sources.py`

## Approach

1. Treat the registry and public exports as the factual source for the current
   API and provider list. Review them before writing prose.
2. Show two deliberately separate consumer flows: ordinary local alerts and
   storm-context/proximity lookup. Make the combination responsibility of
   `wevva`, including its own display, cache, and risk wording choices.
3. Use explicit language such as “contains a forecast cone” and “contains an
   official watch/warning polygon”; never collapse them into “is warned.”
4. Keep source details compact: issuer, basin, language, system identity,
   available geometry kinds, and known limitations.
5. Update the documentation as tasks 0003--0008 land, rather than documenting
   planned capability as released behaviour.

## Acceptance criteria

- A caller can identify the correct public tropical query for source,
  proximity, and match-evidence use without importing internals.
- The documentation explains why a tropical result is separate from ordinary
  `Alert` output and country candidate caching.
- Every documented source and geometry layer corresponds to an implemented,
  tested registry/backend capability.
- A `wevva` maintainer can decide how to render nearby-centre, cone, wind, and
  official-watch/warning matches without guessing their equivalence.
- The architecture and README agree with one another and with the code.

## Verification

- Review all public examples against the current exported signatures.
- Run the CLI help for tropical commands and ensure the documented flags
  exist.
- Run `uv run python -m unittest discover -s tests -v` after any example or
  CLI-related changes.

## Decisions and notes

- Documentation is part of the safety boundary for this feature: spatial
  products are useful precisely because they are not interchangeable.
- The coverage table should be updated in the same change as every new
  tropical source.

## Outcome

Not started.
