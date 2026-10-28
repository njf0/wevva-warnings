"""U.S. National Weather Service backend."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .base import BackendError, WarningBackend, fetch_json
from .._debug import emit_progress
from ..models import Alert
from ..sources import WarningSource


_AFFECTED_ZONES_PARAMETER = 'affectedZones'
_NWS_ZONE_URL_RE = re.compile(
    r'^/zones/(?:forecast|county|fire|marine)/[A-Za-z0-9]+/?$',
    re.IGNORECASE,
)


class NWSBackend(WarningBackend):
    """Fetch alerts from the official NWS API."""

    backend_id = 'nws'
    uses_native_point_query = True

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for an NWS source.

        Parameters
        ----------
        source : WarningSource
            Source definition to query.
        lat : float | None, optional
            Latitude used for the native NWS point query.
        lon : float | None, optional
            Longitude used for the native NWS point query.
        lang : str | None, optional
            Unused for this backend. Included for interface compatibility.
        debug : bool, optional
            If True, log fetch failures.

        Returns
        -------
        list[Alert]
            Alerts returned by the NWS API for the requested source.

        """
        del lang
        if not source.url:
            return []

        params: dict[str, object] | None = None
        if lat is not None and lon is not None:
            params = {'point': f'{lat:.4f},{lon:.4f}'}

        try:
            payload = fetch_json(
                source.url,
                params=params,
                headers={'Accept': 'application/geo+json'},
                debug=debug,
            )
        except BackendError:
            return []

        features = payload.get('features')
        if not isinstance(features, list):
            return []

        alerts: list[Alert] = []
        for feature in features:
            alert = self._to_alert(source, feature)
            if alert is not None:
                alerts.append(alert)
        _enrich_missing_geometries(alerts, source=source, debug=debug)
        return alerts

    def _to_alert(self, source: WarningSource, feature: Any) -> Alert | None:
        """Convert one NWS feature into a normalized alert.

        Parameters
        ----------
        source : WarningSource
            Source definition the feature came from.
        feature : Any
            GeoJSON feature to convert.

        Returns
        -------
        Alert | None
            Normalized alert if the feature is valid, otherwise ``None``.

        """
        if not isinstance(feature, dict):
            return None

        properties = feature.get('properties')
        if not isinstance(properties, dict):
            properties = {}

        event = self.text_or_none(properties.get('event')) or 'Weather Alert'
        headline = self.text_or_none(properties.get('headline')) or event
        identifier = self.text_or_none(properties.get('id')) or self.text_or_none(feature.get('id')) or headline
        alert_url = self.text_or_none(properties.get('@id'))
        if not alert_url:
            feature_id = self.text_or_none(feature.get('id'))
            if feature_id and feature_id.startswith(('http://', 'https://')):
                alert_url = feature_id

        geometry = feature.get('geometry')
        if not isinstance(geometry, dict):
            geometry = None

        geocodes = _normalize_named_values(properties.get('geocode'))
        parameters = _normalize_named_values(properties.get('parameters'))
        affected_zones = _normalize_string_values(properties.get('affectedZones'))
        if affected_zones:
            values = parameters.setdefault(_AFFECTED_ZONES_PARAMETER, [])
            values.extend(zone_url for zone_url in affected_zones if zone_url not in values)

        return Alert(
            id=identifier,
            source=source.id,
            event=event,
            headline=headline,
            url=alert_url,
            severity=self.text_or_none(properties.get('severity')),
            urgency=self.text_or_none(properties.get('urgency')),
            certainty=self.text_or_none(properties.get('certainty')),
            description=self.text_or_none(properties.get('description')),
            instruction=self.text_or_none(properties.get('instruction')),
            onset=self.parse_datetime(properties.get('onset') or properties.get('effective') or properties.get('sent')),
            expires=self.parse_datetime(properties.get('ends') or properties.get('expires')),
            area_names=self.split_areas(properties.get('areaDesc')),
            geocodes=geocodes,
            parameters=parameters,
            geometry=geometry,
        )


def _normalize_named_values(value: object) -> dict[str, list[str]]:
    """Return string or string-list values grouped under their original keys."""
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for raw_name, raw_values in value.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        values = _normalize_string_values(raw_values)
        if values:
            normalized[raw_name] = values
    return normalized


def _normalize_string_values(value: object) -> list[str]:
    """Return distinct non-empty strings from one scalar or list value."""
    raw_values = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, str):
            continue
        text = raw_value.strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _enrich_missing_geometries(
    alerts: list[Alert],
    *,
    source: WarningSource,
    debug: bool,
) -> None:
    """Backfill geometryless alerts from their official NWS affected zones."""
    zone_urls_by_alert: list[tuple[Alert, list[str]]] = []
    requested_urls: dict[str, None] = {}
    for alert in alerts:
        if alert.geometry is not None:
            continue
        zone_urls: list[str] = []
        for value in alert.parameters.get(_AFFECTED_ZONES_PARAMETER, []):
            zone_url = _official_zone_url(value)
            if zone_url is None or zone_url in zone_urls:
                continue
            zone_urls.append(zone_url)
            requested_urls.setdefault(zone_url, None)
        zone_urls_by_alert.append((alert, zone_urls))

    total = len(requested_urls)
    if total:
        emit_progress(
            'alerts_total',
            source=source.id,
            total=total,
            phase='geometry',
        )

    resolved: dict[str, dict[str, Any]] = {}
    for completed, zone_url in enumerate(requested_urls, start=1):
        try:
            resolved[zone_url] = _fetch_zone_geometry(zone_url, debug)
        except BackendError:
            pass
        emit_progress(
            'alerts_checked',
            source=source.id,
            completed=completed,
            total=total,
            phase='geometry',
        )

    for alert, zone_urls in zone_urls_by_alert:
        geometries = [resolved[zone_url] for zone_url in zone_urls if zone_url in resolved]
        geometry = _combine_polygon_geometries(geometries)
        if geometry is not None:
            alert.geometry = geometry


def _official_zone_url(value: str) -> str | None:
    """Return a canonical supported NWS zone URL, rejecting other references."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != 'https'
        or parsed.hostname is None
        or parsed.hostname.lower() != 'api.weather.gov'
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or _NWS_ZONE_URL_RE.fullmatch(parsed.path) is None
    ):
        return None
    return urlunsplit(('https', 'api.weather.gov', parsed.path.rstrip('/'), '', ''))


@lru_cache(maxsize=2048)
def _fetch_zone_geometry(zone_url: str, debug: bool) -> dict[str, Any]:
    """Fetch and cache one valid polygonal NWS zone boundary.

    Exceptions are intentionally not cached, so a transient zone failure can
    be retried by a later alert fetch.
    """
    payload = fetch_json(
        zone_url,
        headers={'Accept': 'application/geo+json'},
        debug=debug,
    )
    if not isinstance(payload, dict):
        raise BackendError('Invalid NWS zone response')
    geometry = payload.get('geometry')
    if not _polygon_parts(geometry):
        raise BackendError('NWS zone response has no polygonal geometry')
    return geometry


def _combine_polygon_geometries(geometries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Combine valid Polygon and MultiPolygon boundaries into alert geometry."""
    polygons = [polygon for geometry in geometries for polygon in _polygon_parts(geometry)]
    if not polygons:
        return None

    geometry: dict[str, Any]
    if len(polygons) == 1:
        geometry = {'type': 'Polygon', 'coordinates': deepcopy(polygons[0])}
    else:
        geometry = {'type': 'MultiPolygon', 'coordinates': deepcopy(polygons)}
    geometry['bbox'] = _polygon_bbox(polygons)
    return geometry


def _polygon_parts(geometry: object) -> list[list[Any]]:
    """Return valid polygon coordinate parts from one GeoJSON geometry."""
    if not isinstance(geometry, dict):
        return []
    coordinates = geometry.get('coordinates')
    if geometry.get('type') == 'Polygon' and _is_polygon(coordinates):
        return [coordinates]
    if geometry.get('type') != 'MultiPolygon' or not isinstance(coordinates, list):
        return []
    return [polygon for polygon in coordinates if _is_polygon(polygon)]


def _is_polygon(value: object) -> bool:
    """Return whether a value is a minimally valid GeoJSON polygon."""
    if not isinstance(value, list) or not value:
        return False
    for ring in value:
        if not isinstance(ring, list) or len(ring) < 4:
            return False
        positions: list[tuple[float, float]] = []
        for position in ring:
            if (
                not isinstance(position, list)
                or len(position) < 2
                or not isinstance(position[0], (int, float))
                or not isinstance(position[1], (int, float))
            ):
                return False
            positions.append((float(position[0]), float(position[1])))
        if positions[0] != positions[-1]:
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
