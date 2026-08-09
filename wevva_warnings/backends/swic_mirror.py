"""Provider backend for SWIC CAP mirror feeds."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree

from ..geocoding import resolve_alert_geometry
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_cap_documents, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_json


_SWIC_WFS_URL = 'https://severeweather.wmo.int/f/wfs'
_SWIC_FEED_PREFIX_RE = re.compile(r'/v2/cap-alerts/([a-z0-9-]+)/rss\.xml$', re.IGNORECASE)
_SWIC_CAP_PATH_RE = re.compile(r'/v2/cap-alerts/(.+\.xml)$', re.IGNORECASE)
_SWIC_CAPURL_RE = re.compile(r'^[a-z0-9-]+/[a-z0-9._/-]+\.xml$', re.IGNORECASE)
_SWIC_WFS_BATCH_SIZE = 10


class SWICMirrorBackend(WarningBackend):
    """Fetch alerts from severeweather.wmo.int SWIC mirror feeds."""

    backend_id = 'swic_mirror'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a SWIC mirror source."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        alert_urls = _swic_mirror_alert_urls(root, base_url=source.url)
        alerts = fetch_cap_documents(
            source,
            alert_urls,
            preferred_lang=lang or source.lang,
            debug=debug,
        )
        _resolve_packaged_geometries(alerts)
        _enrich_missing_geometries_from_wfs(
            alerts,
            source_url=source.url,
            debug=debug,
        )
        return alerts


def _swic_mirror_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a SWIC mirror RSS feed.

    SWIC feeds can contain long histories of revisions for the same warning
    family. These RSS feeds are ordered newest-first, so when a stable family
    key can be inferred from the item GUID we keep only the first item for that
    family before fetching any linked CAP documents.
    """
    urls: list[str] = []
    seen_families: set[str] = set()
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        url = absolute_url(base_url, child_text(item, 'link'))
        if not (url and url.lower().endswith('.xml') and '/v2/cap-alerts/' in url.lower()):
            continue

        family_key = _swic_family_key(child_text(item, 'guid'))
        if family_key is not None:
            if family_key in seen_families:
                continue
            seen_families.add(family_key)
        urls.append(url)
    return list(dict.fromkeys(urls))


def _swic_family_key(guid: str | None) -> str | None:
    """Return a stable SWIC warning-family key inferred from an RSS GUID."""
    if not guid:
        return None
    text = guid.strip()
    if not text:
        return None

    match = re.match(r'^([^-]+-[^-]+)-\d{4}-\d{2}-\d{2}T', text)
    if match is not None:
        return match.group(1)
    return None


def _resolve_packaged_geometries(alerts: list[Alert]) -> None:
    """Attach supported packaged geometry before consulting the SWIC map."""
    for alert in alerts:
        if alert.geometry is not None:
            continue
        geometry = resolve_alert_geometry(alert)
        if geometry is not None:
            alert.geometry = geometry


def _enrich_missing_geometries_from_wfs(
    alerts: list[Alert],
    *,
    source_url: str,
    debug: bool,
) -> None:
    """Backfill geometry still missing after CAP and packaged resolution.

    WFS requests contain only exact `capurl` values for CAP documents selected
    from the feed. A failed map request must never prevent CAP alerts from
    being returned.
    """
    if not any(alert.geometry is None for alert in alerts):
        return

    feed_prefix = _swic_feed_prefix(source_url)
    if feed_prefix is None:
        return
    cap_urls = {
        capurl
        for alert in alerts
        if alert.geometry is None
        and alert.url is not None
        and (capurl := _swic_relative_capurl(alert.url)) is not None
        and capurl.startswith(f'{feed_prefix}/')
        and _SWIC_CAPURL_RE.fullmatch(capurl) is not None
    }
    if not cap_urls:
        return

    geometries = _fetch_wfs_geometries(cap_urls, debug=debug)
    for alert in alerts:
        if alert.geometry is not None or alert.url is None:
            continue
        capurl = _swic_relative_capurl(alert.url)
        if capurl is None or capurl not in geometries:
            continue

        geometry, file_name = geometries[capurl]
        alert.geometry = geometry
        _append_parameter(alert, 'Geometry source', 'WMO SWIC WFS')
        if file_name is not None:
            _append_parameter(alert, 'WMO SWIC geometry file', file_name)


def _fetch_wfs_geometries(
    cap_urls: set[str],
    *,
    debug: bool,
) -> dict[str, tuple[dict[str, Any], str | None]]:
    """Fetch exact CAP-URL WFS features in deliberately small batches."""
    geometries: dict[str, tuple[dict[str, Any], str | None]] = {}
    ordered_cap_urls = sorted(cap_urls)
    for start in range(0, len(ordered_cap_urls), _SWIC_WFS_BATCH_SIZE):
        batch = ordered_cap_urls[start : start + _SWIC_WFS_BATCH_SIZE]
        try:
            payload = fetch_json(
                _SWIC_WFS_URL,
                params={
                    'service': 'WFS',
                    'version': '1.1.0',
                    'request': 'GetFeature',
                    'typeName': 'local_postgis:postgis_geojsons',
                    'outputFormat': 'application/json',
                    'cql_filter': _wfs_capurl_filter(batch),
                },
                debug=debug,
            )
        except BackendError:
            break
        geometries.update(_wfs_geometries_by_capurl(payload, set(batch)))
    return geometries


def _wfs_capurl_filter(cap_urls: list[str]) -> str:
    """Return the ECQL disjunction for validated exact SWIC CAP URLs."""
    return ' OR '.join(f"capurl = '{capurl}'" for capurl in cap_urls)


def _swic_feed_prefix(source_url: str) -> str | None:
    """Return the safe SWIC source family encoded in an RSS URL."""
    match = _SWIC_FEED_PREFIX_RE.search(urlsplit(source_url).path)
    return match.group(1) if match is not None else None


def _swic_relative_capurl(url: str) -> str | None:
    """Return SWIC's relative CAP URL used as the WFS join key."""
    match = _SWIC_CAP_PATH_RE.search(urlsplit(url).path)
    return match.group(1) if match is not None else None


def _wfs_geometries_by_capurl(
    payload: object,
    cap_urls: set[str],
) -> dict[str, tuple[dict[str, Any], str | None]]:
    """Return combined polygonal WFS geometry keyed by exact CAP URL."""
    if not isinstance(payload, dict):
        return {}
    features = payload.get('features')
    if not isinstance(features, list):
        return {}

    polygons_by_capurl: dict[str, list[list[Any]]] = {}
    files_by_capurl: dict[str, str] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get('properties')
        if not isinstance(properties, dict):
            continue
        capurl = properties.get('capurl')
        if not isinstance(capurl, str) or capurl not in cap_urls:
            continue

        polygons = _polygon_parts(feature.get('geometry'))
        if not polygons:
            continue
        polygons_by_capurl.setdefault(capurl, []).extend(polygons)

        file_name = properties.get('file_name')
        if isinstance(file_name, str) and file_name.strip():
            files_by_capurl.setdefault(capurl, file_name.strip())

    geometries: dict[str, tuple[dict[str, Any], str | None]] = {}
    for capurl, polygons in polygons_by_capurl.items():
        geometry: dict[str, Any]
        if len(polygons) == 1:
            geometry = {'type': 'Polygon', 'coordinates': polygons[0]}
        else:
            geometry = {'type': 'MultiPolygon', 'coordinates': polygons}
        geometry['bbox'] = _polygon_bbox(polygons)
        geometries[capurl] = (geometry, files_by_capurl.get(capurl))
    return geometries


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


def _append_parameter(alert: Alert, key: str, value: str) -> None:
    """Add a distinct source-detail value without discarding CAP data."""
    values = alert.parameters.setdefault(key, [])
    if value not in values:
        values.append(value)
