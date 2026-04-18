"""Helpers for resolving alert geocodes to geometries."""

from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import Alert, Geocodes, Geometry

_EMMA_PACKAGED_DATASET = 'emma_geocodes_3dp.json.gz'
_EMMA_SOURCE_DATASET_GLOB = 'MeteoAlarm_Geocodes_*.json'
_EMMA_ALIASES_PACKAGED_DATASET = 'emma_aliases.json.gz'
_EMMA_ALIASES_SOURCE_DATASET_GLOB = 'MeteoAlarm_Geocode_Aliases*.json'
_BOM_AMOC_PACKAGED_DATASET = 'bom_amoc_geocodes.json.gz'


def resolve_alert_geometry(alert: Alert) -> Geometry | None:
    """Return the best available geometry for an alert.

    This prefers the alert's own explicit geometry. If none is present, it
    tries to resolve supported geocodes to a geometry.

    """
    if alert.geometry is not None:
        return alert.geometry
    return geometry_from_geocodes(alert.geocodes)


def geometry_from_geocodes(geocodes: Geocodes) -> Geometry | None:
    """Resolve a normalized geocode mapping to one geometry.

    This uses EMMA as the canonical geometry key, resolving direct ``EMMA_ID``
    values first and then any supported alias systems onto EMMA codes.

    """
    codes = _resolve_emma_codes(geocodes)
    geometries: list[Geometry] = []

    if codes:
        index = _load_emma_index()
        for code in codes:
            geometry = index.get(code)
            if geometry is not None:
                geometries.append(geometry)

    bom_codes = geocodes.get('AMOC-AreaCode') or []
    if bom_codes:
        bom_index = _load_bom_amoc_index()
        for code in bom_codes:
            geometry = bom_index.get(code)
            if geometry is not None:
                geometries.append(geometry)

    return _combine_geometries(geometries)


def _resolve_emma_codes(geocodes: Geocodes) -> list[str]:
    """Resolve a geocode mapping to EMMA IDs."""
    resolved: list[str] = []

    for code in geocodes.get('EMMA_ID') or []:
        if code not in resolved:
            resolved.append(code)

    aliases = _load_emma_aliases()
    if not aliases:
        return resolved

    for system, values in geocodes.items():
        if system == 'EMMA_ID':
            continue
        system_aliases = aliases.get(system)
        if system_aliases is None:
            continue
        for value in values:
            for emma_code in system_aliases.get(value, []):
                if emma_code not in resolved:
                    resolved.append(emma_code)
    return resolved


@lru_cache(maxsize=1)
def _load_emma_index() -> dict[str, Geometry]:
    """Load the local Meteoalarm EMMA geometry dataset."""
    dataset_path = _find_emma_dataset_path()
    if dataset_path is None:
        return {}

    if dataset_path.suffix == '.gz':
        with gzip.open(dataset_path, 'rt', encoding='utf-8') as handle:
            payload = json.load(handle)
    else:
        with dataset_path.open(encoding='utf-8') as handle:
            payload = json.load(handle)

    features = payload.get('features')
    if not isinstance(features, list):
        return {}

    index: dict[str, Geometry] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get('properties')
        geometry = feature.get('geometry')
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        if properties.get('type') != 'EMMA_ID':
            continue
        code = properties.get('code')
        if isinstance(code, str) and code:
            index[code] = geometry
    return index


@lru_cache(maxsize=1)
def _load_emma_aliases() -> dict[str, dict[str, list[str]]]:
    """Load the local EMMA alias dataset."""
    dataset_path = _find_emma_aliases_path()
    if dataset_path is None:
        return {}

    if dataset_path.suffix == '.gz':
        with gzip.open(dataset_path, 'rt', encoding='utf-8') as handle:
            payload = json.load(handle)
    else:
        with dataset_path.open(encoding='utf-8') as handle:
            payload = json.load(handle)

    aliases: dict[str, dict[str, list[str]]] = {}
    for system, mapping in payload.items():
        if not isinstance(system, str) or not isinstance(mapping, dict):
            continue
        normalized_mapping: dict[str, list[str]] = {}
        for code, emma_codes in mapping.items():
            if not isinstance(code, str):
                continue
            if isinstance(emma_codes, str):
                normalized_mapping[code] = [emma_codes]
            elif isinstance(emma_codes, list):
                normalized_mapping[code] = [
                    emma_code for emma_code in emma_codes if isinstance(emma_code, str) and emma_code
                ]
        if normalized_mapping:
            aliases[system] = normalized_mapping
    return aliases


def _find_emma_dataset_path() -> Path | None:
    """Return the first available EMMA dataset path."""
    package_data_dir = Path(__file__).resolve().parent / 'data'
    root_dir = Path(__file__).resolve().parent.parent
    candidates = [
        package_data_dir / _EMMA_PACKAGED_DATASET,
        *sorted(root_dir.glob(_EMMA_SOURCE_DATASET_GLOB), reverse=True),
    ]
    return next((path for path in candidates if path.exists()), None)


def _find_emma_aliases_path() -> Path | None:
    """Return the first available EMMA aliases dataset path."""
    package_data_dir = Path(__file__).resolve().parent / 'data'
    root_dir = Path(__file__).resolve().parent.parent
    candidates = [
        package_data_dir / _EMMA_ALIASES_PACKAGED_DATASET,
        *sorted(root_dir.glob(_EMMA_ALIASES_SOURCE_DATASET_GLOB), reverse=True),
    ]
    return next((path for path in candidates if path.exists()), None)


@lru_cache(maxsize=1)
def _load_bom_amoc_index() -> dict[str, Geometry]:
    """Load the local BoM AMOC geometry dataset."""
    dataset_path = _find_bom_amoc_dataset_path()
    if dataset_path is None:
        return {}

    if dataset_path.suffix == '.gz':
        with gzip.open(dataset_path, 'rt', encoding='utf-8') as handle:
            payload = json.load(handle)
    else:
        with dataset_path.open(encoding='utf-8') as handle:
            payload = json.load(handle)

    mapping = payload.get('AMOC-AreaCode')
    if not isinstance(mapping, dict):
        return {}

    index: dict[str, Geometry] = {}
    for code, geometry in mapping.items():
        if isinstance(code, str) and isinstance(geometry, dict):
            index[code] = geometry
    return index


def _find_bom_amoc_dataset_path() -> Path | None:
    """Return the packaged BoM AMOC dataset path when available."""
    dataset_path = Path(__file__).resolve().parent / 'data' / _BOM_AMOC_PACKAGED_DATASET
    return dataset_path if dataset_path.exists() else None


def _combine_geometries(geometries: list[Geometry]) -> Geometry | None:
    """Combine Polygon and MultiPolygon geometries into one geometry."""
    polygons: list[Any] = []
    for geometry in geometries:
        coordinates = geometry.get('coordinates')
        if geometry.get('type') == 'Polygon' and isinstance(coordinates, list):
            polygons.append(coordinates)
        elif geometry.get('type') == 'MultiPolygon' and isinstance(coordinates, list):
            polygons.extend(coordinates)

    if not polygons:
        return None
    if len(polygons) == 1:
        return {'type': 'Polygon', 'coordinates': polygons[0]}
    return {'type': 'MultiPolygon', 'coordinates': polygons}
