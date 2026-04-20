"""Build a compact packaged JMA area geocode dataset from official GIS shapefiles."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
import shutil
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

DEFAULT_OUTPUT = Path('wevva_warnings/data/jma_area_geocodes')
DEFAULT_USER_AGENT = 'wevva-warnings-jma-builder/0.1'
DEFAULT_PRODUCTS = (
    '1saibun',
    'matome',
    'weather',
)
DEFAULT_PRODUCT_URLS = {
    '1saibun': 'https://www.data.jma.go.jp/developer/gis/20190125_AreaForecastLocalM_1saibun_GIS.zip',
    'matome': 'https://www.data.jma.go.jp/developer/gis/20230517_AreaForecastLocalM_matome_GIS.zip',
    'weather': 'https://www.data.jma.go.jp/developer/gis/20241025_AreaInformationCity_weather_GIS.zip',
}
console = Console()


def main() -> None:
    """Build the packaged JMA area geometry dataset."""
    parser = argparse.ArgumentParser(
        description='Normalize JMA area-code boundary shapefiles to a compact JSON artifact.',
    )
    parser.add_argument(
        'inputs',
        nargs='*',
        type=Path,
        help='Optional local shapefile ZIP inputs. If omitted, known JMA GIS products are fetched.',
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
    resolved_inputs: list[tuple[str, Path]] = []
    input_descriptions: list[str] = []
    input_sizes: list[int] = []

    with TemporaryDirectory() as tmpdir:
        download_dir = Path(tmpdir)

        with Progress(
            SpinnerColumn(),
            TextColumn('[progress.description]{task.description}'),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            fetch_task = progress.add_task('Resolving JMA shapefile inputs', total=len(input_paths))
            detail_task = progress.add_task('Waiting for JMA shapefiles', total=None)

            for input_path in input_paths:
                if input_path.exists():
                    local_path = input_path
                    resolved_inputs.append((input_path.name, local_path))
                    input_descriptions.append(str(input_path))
                    input_sizes.append(local_path.stat().st_size)
                    progress.update(detail_task, description=f'Using local ZIP: {input_path.name}')
                    progress.advance(fetch_task)
                    continue

                product_code = input_path.stem
                url = DEFAULT_PRODUCT_URLS.get(product_code)
                if url is None:
                    raise SystemExit(
                        f'Input file not found and no default download URL is known for {input_path}. '
                        'Pass an explicit local ZIP path.'
                    )
                target_path = download_dir / f'{product_code}.zip'
                progress.update(detail_task, description=f'Downloading JMA ZIP: {product_code}')
                _download_zip(url, target_path)
                resolved_inputs.append((target_path.name, target_path))
                input_descriptions.append(url)
                input_sizes.append(target_path.stat().st_size)
                progress.advance(fetch_task)

            build_task = progress.add_task('Extracting JMA area geometries', total=len(resolved_inputs))
            summary = _build_payload(
                resolved_inputs,
                precision=args.precision,
                output_dir=args.output,
                progress=progress,
                task_id=build_task,
                detail_task_id=detail_task,
            )

            progress.update(detail_task, description='Completed JMA area packaging')

    console.print('[bold]Inputs[/bold]:')
    for description, size in zip(input_descriptions, input_sizes, strict=False):
        console.print(f'  - {description} ({size / 1024 / 1024:.2f} MiB)')
    output_size = sum(path.stat().st_size for path in args.output.glob('*.json.gz')) if args.output.exists() else 0
    console.print(f'[bold]Output[/bold]: {args.output} ({output_size / 1024 / 1024:.2f} MiB total)')
    console.print(
        '[bold]Captured[/bold]: '
        f"{summary['captured_codes']} codes from {summary['products']} products, "
        f"{summary['layers_seen']} shapefiles, {summary['records_seen']} records"
    )
    console.print(f"[bold]Code lengths[/bold]: {summary['length_counts']}")
    if summary['sample_codes']:
        console.print(f"[bold]Sample codes[/bold]: {', '.join(summary['sample_codes'])}")


def _download_zip(url: str, destination: Path) -> None:
    """Download one JMA GIS ZIP."""
    request = Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
    with urlopen(request, timeout=180) as response:
        with destination.open('wb') as handle:
            shutil.copyfileobj(response, handle)


def _build_payload(
    inputs: list[tuple[str, Path]],
    *,
    precision: int,
    output_dir: Path,
    progress: Progress,
    task_id: Any,
    detail_task_id: Any,
) -> dict[str, Any]:
    """Build the packaged JMA area payload files."""
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

    length_counts: Counter[int] = Counter()
    sample_codes: list[str] = []
    layers_seen = 0
    records_seen = 0
    captured_codes_seen: set[str] = set()
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob('*.json.gz'):
        existing.unlink()
    progress.update(task_id, total=len(inputs), completed=0)
    for name, zip_path in inputs:
        progress.update(task_id, description=f'Extracting JMA area geometries ({name})')
        captured_codes, layers_here, records_here = _consume_zip(
            name,
            zip_path,
            precision=precision,
            output_dir=output_dir,
            shapefile_module=shapefile,
            progress=progress,
            detail_task_id=detail_task_id,
        )
        layers_seen += layers_here
        records_seen += records_here
        for code in captured_codes:
            captured_codes_seen.add(code)
            length_counts[len(code)] += 1
            if len(sample_codes) < 8:
                sample_codes.append(code)
        progress.advance(task_id)
    summary = {
        'products': len(inputs),
        'layers_seen': layers_seen,
        'records_seen': records_seen,
        'captured_codes': len(captured_codes_seen),
        'length_counts': ', '.join(f'{length}d={count}' for length, count in sorted(length_counts.items())) or 'none',
        'sample_codes': sample_codes,
    }
    return summary


def _consume_zip(
    name: str,
    zip_path: Path,
    *,
    precision: int,
    output_dir: Path,
    shapefile_module: Any,
    progress: Progress,
    detail_task_id: Any,
) -> tuple[list[str], int, int]:
    """Extract polygon features from one JMA shapefile ZIP payload."""
    captured_codes: list[str] = []
    layers_seen = 0
    records_seen = 0
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with ZipFile(zip_path) as archive:
            archive.extractall(tmp_path)

        shp_files = sorted(tmp_path.rglob('*.shp'))
        for shp_file in shp_files:
            progress.update(detail_task_id, description=f'Inspecting {name}: {shp_file.name}')
            reader = shapefile_module.Reader(str(shp_file), encoding='cp932', encodingErrors='replace')
            field_specs = {field[0]: field for field in reader.fields[1:]}
            code_field = _pick_code_field(reader, field_specs)
            if code_field is None:
                continue

            layers_seen += 1
            progress.update(detail_task_id, description=f'Extracting {name}: {shp_file.name} [{code_field}]')
            width = field_specs[code_field][2]
            for record in reader.iterShapeRecords():
                records_seen += 1
                raw_code = record.record.as_dict().get(code_field)
                code = _normalize_code(raw_code, width=width)
                if code is None:
                    continue
                geometry = record.shape.__geo_interface__
                geometry_type = geometry.get('type')
                if geometry_type not in {'Polygon', 'MultiPolygon'}:
                    continue
                normalized_geometry = _normalize_geometry(geometry, precision=precision)
                bbox = _geometry_bbox(normalized_geometry)
                if bbox is None:
                    continue
                payload = {
                    'geometry': normalized_geometry,
                    'bbox': bbox,
                }
                with gzip.open(output_dir / f'{code}.json.gz', 'wt', encoding='utf-8', compresslevel=9) as handle:
                    json.dump(payload, handle, separators=(',', ':'), ensure_ascii=False)
                captured_codes.append(code)
    return captured_codes, layers_seen, records_seen


def _pick_code_field(reader: Any, field_specs: dict[str, tuple[Any, ...]]) -> str | None:
    """Return the most likely JMA area-code field name for one shapefile."""
    sample_records = []
    for index, record in enumerate(reader.iterRecords()):
        sample_records.append(record.as_dict())
        if index >= 9:
            break

    best_field: str | None = None
    best_score = 0
    for field_name, field in field_specs.items():
        width = field[2]
        score = 0
        lowered = field_name.lower()
        if 'code' in lowered:
            score += 3
        if lowered.endswith('cd'):
            score += 2

        for record in sample_records:
            code = _normalize_code(record.get(field_name), width=width)
            if code is None:
                continue
            score += 2
            if len(code) == 7:
                score += 1
        if score > best_score:
            best_field = field_name
            best_score = score

    return best_field if best_score >= 8 else None


def _normalize_code(value: object, *, width: int) -> str | None:
    """Normalize a JMA area code from a DBF value."""
    if isinstance(value, int):
        text = str(value).zfill(width)
    elif isinstance(value, float):
        if not value.is_integer():
            return None
        text = str(int(value)).zfill(width)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None

    digits = ''.join(ch for ch in text if ch.isdigit())
    if len(digits) not in {6, 7}:
        return None
    return digits


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


def _geometry_bbox(geometry: dict[str, Any]) -> list[float] | None:
    """Return [min_lon, min_lat, max_lon, max_lat] for one geometry."""
    geometry_type = geometry.get('type')
    coordinates = geometry.get('coordinates')
    positions: list[tuple[float, float]] = []

    if geometry_type == 'Polygon' and isinstance(coordinates, list):
        for ring in coordinates:
            for point in ring:
                if isinstance(point, list) and len(point) >= 2:
                    positions.append((float(point[0]), float(point[1])))
    elif geometry_type == 'MultiPolygon' and isinstance(coordinates, list):
        for polygon in coordinates:
            for ring in polygon:
                for point in ring:
                    if isinstance(point, list) and len(point) >= 2:
                        positions.append((float(point[0]), float(point[1])))

    if not positions:
        return None

    longitudes = [position[0] for position in positions]
    latitudes = [position[1] for position in positions]
    return [
        round(min(longitudes), 3),
        round(min(latitudes), 3),
        round(max(longitudes), 3),
        round(max(latitudes), 3),
    ]


if __name__ == '__main__':
    main()
