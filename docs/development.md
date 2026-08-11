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
entry point. There is no publishing configuration or CI release workflow:
releases are deliberate maintainer actions using uv's authenticated PyPI
credentials.

For a normal release, start from the intended complete working tree and use
this sequence. Replace the commit message and bump type where appropriate.

```bash
git status --short
git diff --check

uv version --bump minor
uv run python -m unittest discover -s tests -v

rm -rf dist/
uv build

git status --short
git diff --check
git add -A
git diff --cached --check
git diff --cached --stat
git commit -m "Release 0.5.0"
git tag -a v0.5.0 -m "Release 0.5.0"
git push origin main
git push origin v0.5.0

uv publish
```

`uv version --bump minor` updates `pyproject.toml` and refreshes `uv.lock`.
Use `patch` for a compatible bug fix or `major` for an intentional breaking
release. `rm -rf dist/` is safe here because `dist/` contains only generated,
ignored release artifacts; removing it prevents a previous version's files
being published by mistake. If no credential is active, first run
`uv auth login https://upload.pypi.org/legacy/`.

Never retry a failed upload by rebuilding and publishing the same version:
PyPI filenames are immutable. If PyPI already has one of the version's files,
verify what was uploaded and make a new version for any changed artifact.
