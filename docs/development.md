# Development

## Setup

Python 3.12 or later is required (`pyproject.toml`). Dependencies are declared
in `pyproject.toml` and locked in `uv.lock`; use `uv` for a reproducible local
environment:

```bash
uv sync
```

The package has runtime dependencies on `pyshp`, `rich`, and `typer`.

## Verification

Tests use the standard-library `unittest` framework and mocked provider
payloads:

```bash
uv run python -m unittest discover -s tests -v
```

There is no configured formatter, linter, type checker, pre-commit hook, or CI
workflow. Do not add a new tool incidentally to a feature task.

Build the distribution with setuptools through uv:

```bash
uv build
```

This writes a source distribution and wheel to ignored `dist/`.

## Provider and geometry work

Tests should be deterministic and should mock upstream requests. A live source
check is useful for diagnosis but is not a stable test: official feeds can be
empty, revised, or temporarily unavailable.

`scripts/build_emma_geocodes.py`, `build_emma_aliases.py`,
`build_bom_amoc_geocodes.py`, and `build_jma_area_geocodes.py` build packaged
geocode artifacts. They consume external source data; the README records that
the Meteoalarm aliases download requires a manual Google Drive download. No
application credentials or API keys are configured in this repository.

## Packaging and releases

Setuptools is the build backend. Version and package metadata live in
`pyproject.toml`; `wevva-warnings = wevva_warnings.cli:main` is the console
entry point. No publishing configuration, CI release workflow, or documented
release procedure exists. Releases are manual and use the maintainer's PyPI
token:

1. Update the version in `pyproject.toml` and the local package entry in
   `uv.lock`.
2. Run the full unittest suite and `uv build`.
3. Inspect the generated `dist/` wheel and source distribution, then commit
   the release changes, create a matching `vX.Y.Z` tag, and push the commit and
   tag.
4. Publish the verified artifacts with `uv publish`. Do not place a token in
   the repository; provide it through uv's supported credential mechanism.
