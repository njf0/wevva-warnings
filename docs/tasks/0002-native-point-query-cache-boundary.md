# Task 0002: Native point-query cache boundary

## Status

Completed

## Context

Country-level candidates can be cached and matched locally only for backends
that do not require a point-specific upstream request. A native point-query
backend may return valid point results without usable local geometry.

## Desired outcome

Expose a small public split that lets consumers cache only reusable candidates,
fetch only native point results for a location, and deduplicate the combined
alerts without importing backend internals.

## Scope

- Add and export `get_reusable_alerts_for_country()` for non-native backends.
- Add and export `get_native_alerts_for_point()` for native point-query
  backends.
- Add and export `deduplicate_alerts()` for combined point-result lists.
- Preserve existing `get_alerts_for_country()` and `get_alerts_for_point()`
  behaviour.

## Verification

- Use fake mixed-capability backends to verify each split path calls only its
  respective backend, preserves language and `active_only`, and emits progress
  for only selected sources.
- Run the complete unittest suite and build the distribution.

## Outcome

The public split is driven solely by `uses_native_point_query`. Consumers own
their cache and can keep non-native country candidates separate from results
that must be fetched for each location.
