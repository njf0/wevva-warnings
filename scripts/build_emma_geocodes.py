"""Build a compact packaged EMMA geocode dataset from a Meteoalarm export."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

DEFAULT_OUTPUT = Path('wevva_warnings/data/emma_geocodes_3dp.json.gz')
DEFAULT_INPUT_GLOB = 'MeteoAlarm_Geocodes_*.json'
DEFAULT_SOURCE_URL = (
    'https://gitlab.com/meteoalarm-pm-group/documents/-/raw/master/MeteoAlarm_Geocodes_2026_02_20.json?inline=false'
)
DEFAULT_USER_AGENT = 'wevva-warnings-emma-builder/0.1'
console = Console()


def main() -> None:
    """Build the packaged EMMA dataset."""
    parser = argparse.ArgumentParser(
        description='Round and compress a Meteoalarm EMMA geocode export.',
    )
    parser.add_argument(
        'input',
        nargs='?',
        type=Path,
        help='Path to the upstream Meteoalarm geocode JSON export.',
    )
    parser.add_argument(
        'output',
        nargs='?',
        type=Path,
        default=DEFAULT_OUTPUT,
        help='Path to write the packaged .json.gz artifact.',
    )
    parser.add_argument(
        '--precision',
        type=int,
        default=3,
        help='Decimal places to keep for coordinates (default: 3).',
    )
    parser.add_argument(
        '--url',
        default=DEFAULT_SOURCE_URL,
        help='URL to fetch when no local input file is supplied.',
    )
    args = parser.parse_args()

    input_path = args.input or _discover_input_path()
    input_label = str(input_path) if input_path is not None else args.url
    input_size: int | None = input_path.stat().st_size if input_path is not None and input_path.exists() else None

    with Progress(
        SpinnerColumn(),
        TextColumn('[progress.description]{task.description}'),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        load_task = progress.add_task('Loading upstream EMMA dataset', total=None)
        if input_path is not None:
            if not input_path.exists():
                raise SystemExit(f'Input file does not exist: {input_path}')
            with input_path.open(encoding='utf-8') as handle:
                payload = json.load(handle)
        else:
            payload_bytes = _download_source(args.url)
            input_size = len(payload_bytes)
            payload = json.loads(payload_bytes.decode('utf-8'))
        progress.update(load_task, completed=1, total=1)

        process_task = progress.add_task('Rounding and reducing feature geometry', total=None)
        reduced, summary = _build_reduced_payload(payload, precision=args.precision, progress=progress, task_id=process_task)
        encoded = json.dumps(reduced, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        progress.update(process_task, completed=summary['kept_features'], total=summary['total_features'])

        write_task = progress.add_task('Writing packaged artifact', total=None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(args.output, 'wb', compresslevel=9) as handle:
            handle.write(encoded)
        progress.update(write_task, completed=1, total=1)

    console.print(f'[bold]Input[/bold] : {input_label} ({_format_mib(input_size)})')
    console.print(f'[bold]Output[/bold]: {args.output} ({_format_mib(args.output.stat().st_size)})')
    console.print(
        '[bold]Captured[/bold]: '
        f"{summary['kept_features']} / {summary['total_features']} features, "
        f"{summary['countries']} countries, "
        f"{summary['geometry_types']}"
    )
    if summary['sample_codes']:
        console.print(f"[bold]Sample codes[/bold]: {', '.join(summary['sample_codes'])}")


def _discover_input_path() -> Path | None:
    """Return the newest matching upstream export in the repo root."""
    candidates = sorted(Path.cwd().glob(DEFAULT_INPUT_GLOB), reverse=True)
    return candidates[0] if candidates else None


def _download_source(url: str) -> bytes:
    """Download the upstream EMMA source JSON."""
    request = Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
    with urlopen(request, timeout=180) as response:
        return response.read()


def _build_reduced_payload(
    payload: dict[str, Any],
    *,
    precision: int,
    progress: Progress,
    task_id: TaskID,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a compact FeatureCollection with rounded coordinates."""
    features = payload.get('features')
    if not isinstance(features, list):
        raise SystemExit('Input payload does not contain a GeoJSON FeatureCollection "features" list.')

    reduced_features: list[dict[str, Any]] = []
    countries: set[str] = set()
    geometry_types: Counter[str] = Counter()
    sample_codes: list[str] = []

    progress.update(task_id, total=len(features), completed=0)
    for feature in features:
        if not isinstance(feature, dict):
            progress.advance(task_id)
            continue
        properties = feature.get('properties')
        geometry = feature.get('geometry')
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            progress.advance(task_id)
            continue

        country = properties.get('country')
        if isinstance(country, str) and country:
            countries.add(country)
        geometry_type = geometry.get('type')
        if isinstance(geometry_type, str) and geometry_type:
            geometry_types[geometry_type] += 1
        code = properties.get('code')
        if isinstance(code, str) and code and len(sample_codes) < 5:
            sample_codes.append(code)

        reduced_features.append(
            {
                'type': 'Feature',
                'properties': {
                    'code': code,
                    'country': properties.get('country'),
                    'name': properties.get('name'),
                    'type': properties.get('type'),
                },
                'geometry': _round_nested(geometry, precision=precision),
            }
        )
        progress.advance(task_id)

    summary = {
        'total_features': len(features),
        'kept_features': len(reduced_features),
        'countries': len(countries),
        'geometry_types': ', '.join(f'{name}={count}' for name, count in sorted(geometry_types.items())) or 'none',
        'sample_codes': sample_codes,
    }
    return {'type': 'FeatureCollection', 'features': reduced_features}, summary


def _round_nested(value: Any, *, precision: int) -> Any:
    """Round floats recursively inside nested JSON-like data."""
    if isinstance(value, float):
        return round(value, precision)
    if isinstance(value, list):
        return [_round_nested(item, precision=precision) for item in value]
    if isinstance(value, dict):
        return {key: _round_nested(item, precision=precision) for key, item in value.items()}
    return value


def _format_mib(size_bytes: int) -> str:
    """Return a human-readable MiB size string."""
    return f'{size_bytes / 1024 / 1024:.2f} MiB'


if __name__ == '__main__':
    main()
