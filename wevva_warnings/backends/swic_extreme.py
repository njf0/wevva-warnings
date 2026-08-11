"""Global Extreme-warning discovery from WMO SWIC map features."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

from ..models import Alert
from ..sources import WarningSource
from .base import BackendError, WarningBackend, fetch_json


_SWIC_WFS_URL = 'https://severeweather.wmo.int/f/wfs'
_SWIC_CAP_URL = 'https://severeweather.wmo.int/v2/cap-alerts/'
_SWIC_CAPURL_RE = re.compile(r'^[a-z0-9-]+/[a-z0-9._/-]+\.xml$', re.IGNORECASE)
_SWIC_WFS_TIMEOUT = 30.0


class SWICExtremeBackend(WarningBackend):
    """Fetch WMO SWIC map features classified with Extreme severity."""

    backend_id = 'swic_extreme'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
        include_marine: bool = False,
    ) -> list[Alert]:
        """Return SWIC's mapped Extreme-warning candidates.

        The global WFS has no language or point-query contract. ``lat`` and
        ``lon`` are accepted only to satisfy the shared backend boundary and
        are deliberately ignored.
        """
        del lat, lon, lang
        try:
            payload = fetch_json(
                _SWIC_WFS_URL,
                params={
                    'service': 'WFS',
                    'version': '1.1.0',
                    'request': 'GetFeature',
                    'typeName': 'local_postgis:postgis_geojsons',
                    'outputFormat': 'application/json',
                    'cql_filter': _wfs_extreme_filter(include_marine=include_marine),
                },
                timeout=_SWIC_WFS_TIMEOUT,
                debug=debug,
            )
        except BackendError:
            return []
        return _alerts_from_wfs(payload, source=source, include_marine=include_marine)


def _wfs_extreme_filter(*, include_marine: bool) -> str:
    """Return the bounded SWIC WFS filter for mapped Extreme warnings."""
    if include_marine:
        return 's = 4'
    return "s = 4 AND marine = '0'"


def _alerts_from_wfs(
    payload: object,
    *,
    source: WarningSource,
    include_marine: bool,
) -> list[Alert]:
    """Normalize and group valid polygonal WFS features by exact CAP URL."""
    if not isinstance(payload, dict):
        return []
    features = payload.get('features')
    if not isinstance(features, list):
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get('properties')
        if not isinstance(properties, dict):
            continue
        capurl = properties.get('capurl')
        if not isinstance(capurl, str) or _SWIC_CAPURL_RE.fullmatch(capurl) is None:
            continue
        if not include_marine and _is_marine(properties.get('marine')):
            continue
        polygons = _polygon_parts(feature.get('geometry'))
        if not polygons:
            continue
        grouped.setdefault(capurl, []).append({'properties': properties, 'polygons': polygons})

    alerts: list[Alert] = []
    for capurl in sorted(grouped):
        rows = grouped[capurl]
        properties = rows[0]['properties']
        polygons = [polygon for row in rows for polygon in row['polygons']]
        area_names = _distinct_text(row['properties'].get('areadesc') for row in rows)
        event = WarningBackend.text_or_none(properties.get('event')) or 'Weather warning'
        headline = WarningBackend.text_or_none(properties.get('headline')) or _headline(event, area_names)
        description = WarningBackend.text_or_none(properties.get('description'))
        if description == 'No description':
            description = None

        parameters = {
            'WMO SWIC CAP URL': [capurl],
            'WMO SWIC Severity Code': [str(properties.get('s', 4))],
        }
        _add_parameter(properties, parameters, 'u', 'WMO SWIC Urgency Code')
        _add_parameter(properties, parameters, 'c', 'WMO SWIC Certainty Code')
        _add_parameter(properties, parameters, 'file_name', 'WMO SWIC geometry file')

        alerts.append(
            Alert(
                id=capurl,
                source=source.id,
                event=event,
                headline=headline,
                url=f'{_SWIC_CAP_URL}{capurl}',
                severity='Extreme',
                description=description,
                onset=WarningBackend.parse_datetime(properties.get('onset') or properties.get('effective')),
                expires=WarningBackend.parse_datetime(properties.get('expires')),
                area_names=area_names,
                parameters=parameters,
                geometry=_combined_geometry(polygons),
            )
        )
    return alerts


def _add_parameter(properties: dict[str, Any], parameters: dict[str, list[str]], key: str, name: str) -> None:
    """Copy one non-empty WFS property to source-specific alert metadata."""
    value = properties.get(key)
    if value is None:
        return
    text = str(value).strip()
    if text:
        parameters[name] = [text]


def _is_marine(value: object) -> bool:
    """Return whether SWIC marks a map feature as marine."""
    return str(value).strip().lower() in {'1', 'true', 'yes'}


def _headline(event: str, area_names: list[str]) -> str:
    """Build a useful fallback when SWIC has no headline text."""
    if not area_names:
        return event
    return f'{event} — {", ".join(area_names)}'


def _distinct_text(values: Iterable[object]) -> list[str]:
    """Return distinct non-empty text values in their first-seen order."""
    result: list[str] = []
    for value in values:
        text = WarningBackend.text_or_none(value)
        if text is not None and text not in result:
            result.append(text)
    return result


def _combined_geometry(polygons: list[list[Any]]) -> dict[str, Any]:
    """Return a Polygon or MultiPolygon with a bounding box."""
    if len(polygons) == 1:
        geometry: dict[str, Any] = {'type': 'Polygon', 'coordinates': polygons[0]}
    else:
        geometry = {'type': 'MultiPolygon', 'coordinates': polygons}
    geometry['bbox'] = _polygon_bbox(polygons)
    return geometry


def _polygon_parts(geometry: object) -> list[list[Any]]:
    """Extract valid GeoJSON Polygon parts from one WFS geometry."""
    if not isinstance(geometry, dict):
        return []
    coordinates = geometry.get('coordinates')
    if geometry.get('type') == 'Polygon' and _is_polygon(coordinates):
        return [coordinates]
    if geometry.get('type') != 'MultiPolygon' or not isinstance(coordinates, list):
        return []
    return [polygon for polygon in coordinates if _is_polygon(polygon)]


def _is_polygon(value: object) -> bool:
    """Return whether *value* has the minimum valid GeoJSON polygon shape."""
    if not isinstance(value, list) or not value:
        return False
    for ring in value:
        if not isinstance(ring, list) or len(ring) < 4:
            return False
        for position in ring:
            if (
                not isinstance(position, list)
                or len(position) < 2
                or not isinstance(position[0], (int, float))
                or not isinstance(position[1], (int, float))
            ):
                return False
    return True


def _polygon_bbox(polygons: list[list[Any]]) -> list[float]:
    """Return the bounding box for validated polygon coordinate lists."""
    positions = [
        (float(position[0]), float(position[1]))
        for polygon in polygons
        for ring in polygon
        for position in ring
    ]
    longitudes, latitudes = zip(*positions, strict=True)
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]
