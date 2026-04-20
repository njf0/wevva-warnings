"""Build a compact packaged BoM AMOC geocode dataset from official shapefiles."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.request import Request, urlopen
from zipfile import ZipFile

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

DEFAULT_OUTPUT = Path('wevva_warnings/data/bom_amoc_geocodes')
DEFAULT_USER_AGENT = 'wevva-warnings-bom-builder/0.1'
DEFAULT_PRODUCTS = ('IDM00001', 'IDM00003', 'IDM00014', 'IDM00017')
DEFAULT_PRODUCT_URLS = {
    'IDM00001': 'ftp://ftp.bom.gov.au/anon/home/adfd/spatial/IDM00001.zip',
    'IDM00003': 'ftp://ftp.bom.gov.au/anon/home/adfd/spatial/IDM00003.zip',
    'IDM00014': 'ftp://ftp.bom.gov.au/anon/home/adfd/spatial/IDM00014.zip',
    'IDM00017': 'ftp://ftp.bom.gov.au/anon/home/adfd/spatial/IDM00017.zip',
}
console = Console()


def main() -> None:
    """Build the packaged BoM AMOC geometry dataset."""
    parser = argparse.ArgumentParser(
        description='Normalize BoM AMOC boundary shapefiles to a compact JSON artifact.',
    )
    parser.add_argument(
        'inputs',
        nargs='*',
        type=Path,
        help='Optional local shapefile ZIP inputs. If omitted, known BoM FTP products are fetched.',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT,
        help='Directory to write packaged per-code .json.gz artifacts into.',
    )
    parser.add_argument(
        '--precision',
        type=int,
        default=3,
        help='Decimal places to keep for coordinates (default: 3).',
    )
    args = parser.parse_args()

    input_paths = args.inputs or [Path(f'{code}.zip') for code in DEFAULT_PRODUCTS]
    resolved_inputs: list[tuple[str, bytes]] = []
    input_descriptions: list[str] = []
    input_sizes: list[int] = []

    with Progress(
        SpinnerColumn(),
        TextColumn('[progress.description]{task.description}'),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        fetch_task = progress.add_task('Resolving BoM shapefile inputs', total=len(input_paths))
        for input_path in input_paths:
            if input_path.exists():
                payload_bytes = input_path.read_bytes()
                resolved_inputs.append((input_path.name, payload_bytes))
                input_descriptions.append(str(input_path))
                input_sizes.append(len(payload_bytes))
                progress.advance(fetch_task)
                continue

            product_code = input_path.stem.upper()
            url = DEFAULT_PRODUCT_URLS.get(product_code)
            if url is None:
                raise SystemExit(
                    f'Input file not found and no default download URL is known for {input_path}. '
                    'Pass an explicit local ZIP path.'
                )
            payload_bytes = _download_zip(url)
            resolved_inputs.append((f'{product_code}.zip', payload_bytes))
            input_descriptions.append(url)
            input_sizes.append(len(payload_bytes))
            progress.advance(fetch_task)

        build_task = progress.add_task('Extracting AMOC geometries from shapefiles', total=len(resolved_inputs))
        summary = _build_payload(
            resolved_inputs,
            output_dir=args.output,
            precision=args.precision,
            progress=progress,
            task_id=build_task,
        )

    console.print('[bold]Inputs[/bold]:')
    for description, size in zip(input_descriptions, input_sizes, strict=False):
        console.print(f'  - {description} ({size / 1024 / 1024:.2f} MiB)')
    output_size = sum(path.stat().st_size for path in args.output.glob('*.json.gz')) if args.output.exists() else 0
    console.print(f'[bold]Output[/bold]: {args.output} ({output_size / 1024 / 1024:.2f} MiB total)')
    console.print(
        '[bold]Captured[/bold]: '
        f"{summary['captured_codes']} codes from {summary['products']} products, "
        f"{summary['family_counts']}"
    )
    if summary['sample_codes']:
        console.print(f"[bold]Sample codes[/bold]: {', '.join(summary['sample_codes'])}")
def _download_zip(url: str) -> bytes:
    """Download one BoM shapefile ZIP."""
    request = Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
    with urlopen(request, timeout=180) as response:
        return response.read()


def _build_payload(
    inputs: list[tuple[str, bytes]],
    *,
    output_dir: Path,
    precision: int,
    progress: Progress,
    task_id: Any,
) -> dict[str, Any]:
    """Build the fragmented BoM AMOC payload."""
    try:
        import shapefile  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            'This builder requires the optional "pyshp" package.\n'
            'Install it in your environment first, for example:\n'
            '  uv add pyshp\n'
            'or:\n'
            '  pip install pyshp'
        ) from exc

    family_counts: Counter[str] = Counter()
    sample_codes: list[str] = []
    records_seen = 0
    captured_codes_seen: set[str] = set()
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob('*.json.gz'):
        existing.unlink()
    progress.update(task_id, total=len(inputs), completed=0)
    for name, payload in inputs:
        captured_codes, seen_here = _consume_zip(
            name,
            payload,
            output_dir=output_dir,
            precision=precision,
            shapefile_module=shapefile,
        )
        records_seen += seen_here
        for code in captured_codes:
            captured_codes_seen.add(code)
            family_counts[_family_from_code(code)] += 1
            if len(sample_codes) < 8:
                sample_codes.append(code)
        progress.advance(task_id)
    summary = {
        'products': len(inputs),
        'records_seen': records_seen,
        'captured_codes': len(captured_codes_seen),
        'family_counts': ', '.join(f'{family}={count}' for family, count in sorted(family_counts.items())) or 'none',
        'sample_codes': sample_codes,
    }
    return summary


def _consume_zip(
    name: str,
    payload: bytes,
    *,
    output_dir: Path,
    precision: int,
    shapefile_module: Any,
) -> tuple[list[str], int]:
    """Extract polygon features from one shapefile ZIP payload."""
    captured_codes: list[str] = []
    records_seen = 0
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = tmp_path / name
        zip_path.write_bytes(payload)

        with ZipFile(zip_path) as archive:
            archive.extractall(tmp_path)

        shp_files = sorted(tmp_path.glob('*.shp'))
        if not shp_files:
            return captured_codes, records_seen

        reader = shapefile_module.Reader(str(shp_files[0]))
        field_names = [field[0] for field in reader.fields[1:]]
        code_field = _pick_code_field(field_names)
        if code_field is None:
            return captured_codes, records_seen

        for record in reader.iterShapeRecords():
            records_seen += 1
            code = record.record.as_dict().get(code_field)
            if not isinstance(code, str) or not code:
                continue
            geometry = record.shape.__geo_interface__
            geometry_type = geometry.get('type')
            if geometry_type not in {'Polygon', 'MultiPolygon'}:
                continue
            normalized_geometry = _normalize_geometry(geometry, precision=precision)
            with gzip.open(output_dir / f'{code}.json.gz', 'wt', encoding='utf-8', compresslevel=9) as handle:
                json.dump(normalized_geometry, handle, separators=(',', ':'), ensure_ascii=False)
            captured_codes.append(code)
    return captured_codes, records_seen


def _pick_code_field(field_names: list[str]) -> str | None:
    """Return the most likely AAC field name for a BoM shapefile."""
    candidates = ['AAC', 'AAC_MW', 'AAC_RC', 'AAC_ME', 'AAC_PW', 'AAC_FA', 'AAC_FW']
    return next((name for name in candidates if name in field_names), None)


def _family_from_code(code: str) -> str:
    """Return the BoM area-code family segment from an AAC code."""
    parts = code.split('_', maxsplit=1)
    if len(parts) != 2:
        return 'unknown'
    suffix = parts[1]
    family = ''.join(ch for ch in suffix if ch.isalpha())
    return family or 'unknown'


def _round_nested(value: Any, *, precision: int) -> Any:
    """Round floats recursively inside nested JSON-like data."""
    if isinstance(value, float):
        return round(value, precision)
    if isinstance(value, list):
        return [_round_nested(item, precision=precision) for item in value]
    if isinstance(value, tuple):
        return [_round_nested(item, precision=precision) for item in value]
    if isinstance(value, dict):
        return {key: _round_nested(item, precision=precision) for key, item in value.items()}
    return value


def _normalize_geometry(geometry: dict[str, Any], *, precision: int) -> dict[str, Any]:
    """Round coordinates and conservatively remove duplicate vertices."""
    geometry_type = geometry.get('type')
    coordinates = geometry.get('coordinates')
    if geometry_type == 'Polygon' and isinstance(coordinates, list):
        rings = [_normalize_ring(ring, precision=precision) for ring in coordinates]
        rings = [ring for ring in rings if ring is not None]
        return {'type': 'Polygon', 'coordinates': rings}
    if geometry_type == 'MultiPolygon' and isinstance(coordinates, list):
        polygons: list[list[list[list[float]]]] = []
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            rings = [_normalize_ring(ring, precision=precision) for ring in polygon]
            rings = [ring for ring in rings if ring is not None]
            if rings:
                polygons.append(rings)
        return {'type': 'MultiPolygon', 'coordinates': polygons}
    return _round_nested(geometry, precision=precision)


def _normalize_ring(ring: Any, *, precision: int) -> list[list[float]] | None:
    """Round one ring and collapse consecutive duplicate vertices."""
    if not isinstance(ring, list):
        return None

    points: list[list[float]] = []
    for point in ring:
        if (
            not isinstance(point, (list, tuple))
            or len(point) < 2
            or not isinstance(point[0], (int, float))
            or not isinstance(point[1], (int, float))
        ):
            continue
        rounded = [round(float(point[0]), precision), round(float(point[1]), precision)]
        if not points or points[-1] != rounded:
            points.append(rounded)

    if len(points) < 3:
        return None
    if points[0] != points[-1]:
        points.append(points[0][:])
    elif len(points) >= 2 and points[-2] == points[0]:
        points.pop(-1)
        if points[0] != points[-1]:
            points.append(points[0][:])

    if len(points) < 4:
        return None
    return points


if __name__ == '__main__':
    main()
