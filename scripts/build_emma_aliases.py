"""Build a compact packaged EMMA alias dataset."""

from __future__ import annotations

import argparse
import csv
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

DEFAULT_OUTPUT = Path('wevva_warnings/data/emma_aliases.json')
DEFAULT_INPUT_GLOB = 'MeteoAlarm_Geocode_Aliases*.json'
DEFAULT_INPUT_CSV_GLOB = 'geocodes-aliases*.csv'
DEFAULT_SOURCE_URL = 'https://drive.google.com/uc?export=download&id=1haP3_PFz9nYrEgLjCd_YvaCuMb9_5QC1'
DEFAULT_USER_AGENT = 'wevva-warnings-emma-alias-builder/0.1'
console = Console()


def main() -> None:
    """Build the packaged EMMA aliases dataset."""
    parser = argparse.ArgumentParser(
        description='Normalize Meteoalarm alias mappings to EMMA IDs.',
    )
    parser.add_argument(
        'input',
        nargs='?',
        type=Path,
        help='Path to the upstream Meteoalarm alias JSON export.',
    )
    parser.add_argument(
        'output',
        nargs='?',
        type=Path,
        default=DEFAULT_OUTPUT,
        help='Path to write the packaged .json artifact.',
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
        load_task = progress.add_task('Loading upstream EMMA aliases', total=None)
        if input_path is not None:
            if not input_path.exists():
                raise SystemExit(f'Input file does not exist: {input_path}')
            payload = _load_local_payload(input_path)
        else:
            payload_bytes = _download_source(args.url)
            input_size = len(payload_bytes)
            payload = _decode_downloaded_json(payload_bytes, source_url=args.url)
        progress.update(load_task, completed=1, total=1)

        normalize_task = progress.add_task('Normalizing alias mappings', total=None)
        normalized = _normalize_alias_payload(payload, progress=progress, task_id=normalize_task)
        normalized_count = sum(len(mapping) for mapping in normalized.values())
        progress.update(
            normalize_task,
            total=max(1, normalized_count),
            completed=max(1, normalized_count),
        )

        write_task = progress.add_task('Writing packaged artifact', total=None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('w', encoding='utf-8') as handle:
            json.dump(normalized, handle, separators=(',', ':'), ensure_ascii=False)
        progress.update(write_task, completed=1, total=1)

    summary = _summarize_aliases(normalized)
    console.print(f'[bold]Input[/bold] : {input_label} ({_format_mib(input_size)})')
    console.print(f'[bold]Output[/bold]: {args.output} ({_format_mib(args.output.stat().st_size)})')
    console.print(
        '[bold]Captured[/bold]: '
        f"{summary['systems']} systems, "
        f"{summary['alias_codes']} alias codes, "
        f"{summary['emma_links']} EMMA links"
    )
    if summary['top_systems']:
        console.print(f"[bold]Systems[/bold]: {summary['top_systems']}")
    if summary['sample_mappings']:
        console.print(f"[bold]Sample mappings[/bold]: {summary['sample_mappings']}")


def _discover_input_path() -> Path | None:
    """Return the newest matching alias export in the repo root."""
    candidates = sorted(
        [*Path.cwd().glob(DEFAULT_INPUT_GLOB), *Path.cwd().glob(DEFAULT_INPUT_CSV_GLOB)],
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_local_payload(path: Path) -> Any:
    """Load a local aliases payload from JSON or CSV."""
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def _download_source(url: str) -> bytes:
    """Download the upstream EMMA aliases source JSON."""
    request = Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
    with urlopen(request, timeout=180) as response:
        return response.read()


def _decode_downloaded_json(payload_bytes: bytes, *, source_url: str) -> Any:
    """Decode downloaded JSON and provide a helpful error for HTML responses."""
    text = payload_bytes.decode('utf-8', errors='replace')
    try:
        return json.loads(text)
    except JSONDecodeError as exc:
        preview = text[:200].lstrip().lower()
        if preview.startswith('<!doctype html') or preview.startswith('<html'):
            raise SystemExit(
                'The downloaded aliases source was HTML, not JSON. '
                'This usually means Google Drive returned an interstitial page instead of the raw file.\n'
                f'URL tried: {source_url}\n'
                'Download the aliases file locally in your browser and then run:\n'
                '  python3 scripts/build_emma_aliases.py /path/to/downloaded-aliases.json\n'
                'or, if Meteoalarm gives you a CSV export:\n'
                '  python3 scripts/build_emma_aliases.py /path/to/geocodes-aliases.csv'
            ) from exc
        raise SystemExit(
            'Downloaded aliases source could not be parsed as JSON.\n'
            f'URL tried: {source_url}'
        ) from exc


def _normalize_alias_payload(
    payload: Any,
    *,
    progress: Progress | None = None,
    task_id: Any = None,
) -> dict[str, dict[str, list[str]]]:
    """Return a normalized aliases mapping of system -> code -> EMMA IDs."""
    if isinstance(payload, dict):
        if _looks_like_normalized_alias_payload(payload):
            return _normalize_alias_mapping(payload)
        for key in ('aliases', 'mappings', 'items', 'data'):
            value = payload.get(key)
            if isinstance(value, list):
                return _normalize_alias_records(value, progress=progress, task_id=task_id)
    if isinstance(payload, list):
        return _normalize_alias_records(payload, progress=progress, task_id=task_id)
    raise SystemExit('Unsupported alias payload structure.')


def _looks_like_normalized_alias_payload(payload: dict[str, Any]) -> bool:
    """Return whether the payload already resembles the normalized alias form."""
    if not payload:
        return False
    return all(isinstance(value, dict) for value in payload.values())


def _normalize_alias_mapping(payload: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """Normalize a mapping-shaped alias payload."""
    normalized: dict[str, dict[str, list[str]]] = {}
    for system, mapping in payload.items():
        if not isinstance(system, str) or not isinstance(mapping, dict):
            continue
        system_map = normalized.setdefault(system, {})
        for code, emma_values in mapping.items():
            if not isinstance(code, str):
                continue
            for emma_code in _coerce_code_list(emma_values):
                _append_mapping(system_map, code, emma_code)
    return {system: mapping for system, mapping in normalized.items() if mapping}


def _normalize_alias_records(
    records: list[Any],
    *,
    progress: Progress | None = None,
    task_id: Any = None,
) -> dict[str, dict[str, list[str]]]:
    """Normalize a record-list alias payload."""
    normalized: dict[str, dict[str, list[str]]] = {}
    if progress is not None and task_id is not None:
        progress.update(task_id, total=len(records), completed=0)
    for record in records:
        if not isinstance(record, dict):
            if progress is not None and task_id is not None:
                progress.advance(task_id)
            continue

        emma_code = _pick_string(record, 'CODE')
        alias_code = _pick_string(record, 'ALIAS_CODE')
        alias_type = _pick_string(record, 'ALIAS_TYPE')
        if emma_code and alias_code and alias_type:
            system_map = normalized.setdefault(alias_type, {})
            _append_mapping(system_map, alias_code, emma_code)
            if progress is not None and task_id is not None:
                progress.advance(task_id)
            continue

        if _record_is_emma_with_aliases(record):
            emma_codes = _extract_emma_codes(record)
            aliases = record.get('aliases')
            if isinstance(aliases, list):
                for alias in aliases:
                    alias_type, alias_code = _extract_alias_pair(alias)
                    if alias_type is None or alias_code is None:
                        continue
                    for emma_code in emma_codes:
                        system_map = normalized.setdefault(alias_type, {})
                        _append_mapping(system_map, alias_code, emma_code)
            if progress is not None and task_id is not None:
                progress.advance(task_id)
            continue

        from_type = _pick_string(record, 'from_type', 'source_type', 'alias_type', 'type')
        from_code = _pick_string(record, 'from_code', 'source_code', 'alias_code', 'code')
        to_type = _pick_string(record, 'to_type', 'target_type', 'target_scheme')
        to_code = _pick_string(record, 'to_code', 'target_code', 'emma_id', 'emma', 'value')
        if from_type and from_code and to_type == 'EMMA_ID' and to_code:
            system_map = normalized.setdefault(from_type, {})
            _append_mapping(system_map, from_code, to_code)
        if progress is not None and task_id is not None:
            progress.advance(task_id)
    return {system: mapping for system, mapping in normalized.items() if mapping}


def _record_is_emma_with_aliases(record: dict[str, Any]) -> bool:
    """Return whether a record looks like an EMMA code with attached aliases."""
    return _pick_string(record, 'type', 'code_type') == 'EMMA_ID' and isinstance(record.get('aliases'), list)


def _extract_emma_codes(record: dict[str, Any]) -> list[str]:
    """Return EMMA IDs from a record."""
    codes = _coerce_code_list(record.get('emma_id'))
    if not codes:
        codes = _coerce_code_list(record.get('emma'))
    if not codes and _pick_string(record, 'type', 'code_type') == 'EMMA_ID':
        codes = _coerce_code_list(record.get('code'))
    return codes


def _extract_alias_pair(record: Any) -> tuple[str | None, str | None]:
    """Return one alias system/code pair from a record-like object."""
    if not isinstance(record, dict):
        return None, None
    alias_type = _pick_string(record, 'type', 'alias_type', 'scheme')
    alias_code = _pick_string(record, 'code', 'alias_code', 'value')
    return alias_type, alias_code


def _coerce_code_list(value: Any) -> list[str]:
    """Return a list of non-empty string codes."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _pick_string(record: dict[str, Any], *keys: str) -> str | None:
    """Return the first non-empty string value for any candidate key."""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _append_mapping(system_map: dict[str, list[str]], code: str, emma_code: str) -> None:
    """Append one mapping while preserving insertion order."""
    emma_codes = system_map.setdefault(code, [])
    if emma_code not in emma_codes:
        emma_codes.append(emma_code)


def _summarize_aliases(normalized: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    """Return a compact build summary for console output."""
    alias_codes = sum(len(mapping) for mapping in normalized.values())
    emma_links = sum(len(emma_codes) for mapping in normalized.values() for emma_codes in mapping.values())
    top_systems = ', '.join(
        f'{system}={len(mapping)}'
        for system, mapping in sorted(normalized.items(), key=lambda item: (-len(item[1]), item[0]))[:6]
    )

    sample_mappings: list[str] = []
    for system, mapping in sorted(normalized.items()):
        for code, emma_codes in sorted(mapping.items()):
            sample_mappings.append(f"{system}:{code}->{'/'.join(emma_codes[:2])}")
            if len(sample_mappings) == 5:
                return {
                    'systems': len(normalized),
                    'alias_codes': alias_codes,
                    'emma_links': emma_links,
                    'top_systems': top_systems,
                    'sample_mappings': ', '.join(sample_mappings),
                }

    return {
        'systems': len(normalized),
        'alias_codes': alias_codes,
        'emma_links': emma_links,
        'top_systems': top_systems,
        'sample_mappings': ', '.join(sample_mappings),
    }


def _format_mib(size_bytes: int | None) -> str:
    """Return a human-readable MiB size string."""
    if size_bytes is None:
        return 'unknown size'
    return f'{size_bytes / 1024 / 1024:.2f} MiB'


if __name__ == '__main__':
    main()
