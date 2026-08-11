"""Provider backend for Bureau of Meteorology tropical-track GML products."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin
from xml.etree import ElementTree

from ..models import Alert, Geometry, TropicalSystem
from ..sources import WarningSource
from ._cap_feed import local_name
from .base import BackendError, WarningBackend, fetch_text

_PRODUCT_FILENAMES = frozenset(
    {
        'IDD65401.GML', 'IDD65402.GML', 'IDD65408.GML', 'IDD65409.GML',
        'IDQ65248.GML', 'IDQ65249.GML', 'IDQ65250.GML', 'IDQ65251.GML', 'IDQ65252.GML',
        'IDW60266.GML', 'IDW60267.GML', 'IDW60268.GML', 'IDW60283.GML',
    }
)
_LISTING_FILENAME_RE = re.compile(r'\b([A-Z]{3}\d{5}\.GML)\b', re.IGNORECASE)


class BoMTropicalBackend(WarningBackend):
    """Fetch active Australian-region systems from BoM's public FTP products."""

    backend_id = 'bom_tropical'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return no ordinary alerts for BoM tropical-track products."""
        del source, lat, lon, lang, debug
        return []

    def fetch_tropical_systems(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[TropicalSystem]:
        """Fetch the currently published BoM tropical-track GML products."""
        del lat, lon, lang
        if not source.url:
            return []
        try:
            listing = fetch_text(source.url, debug=debug)
        except BackendError:
            return []

        systems: dict[str, TropicalSystem] = {}
        for product_url in _product_urls(listing, base_url=source.url):
            try:
                payload = fetch_text(product_url, headers={'Accept': 'application/gml+xml, application/xml'}, debug=debug)
            except BackendError:
                continue
            system = _parse_bom_product(payload, source=source.id, url=product_url)
            if system is None:
                continue
            previous = systems.get(system.id)
            if previous is None or _prefer_system(system, previous):
                systems[system.id] = system

        return sorted(systems.values(), key=lambda system: (system.name.casefold(), system.id))


def _product_urls(listing: str, *, base_url: str) -> list[str]:
    filenames: dict[str, str] = {}
    for match in _LISTING_FILENAME_RE.finditer(listing):
        filename = match.group(1)
        product_key = filename.upper()
        if product_key in _PRODUCT_FILENAMES:
            filenames.setdefault(product_key, filename)
    return [urljoin(base_url, filenames[product_key]) for product_key in sorted(filenames)]


def _parse_bom_product(xml_payload: str, *, source: str, url: str) -> TropicalSystem | None:
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return None

    disturbance_id = _descendant_text(root, 'distId')
    name = _descendant_text(root, 'distName')
    if not disturbance_id or not name:
        return None

    current_fix = _current_fix(root)
    center_lat, center_lon = _point_coordinates(current_fix) if current_fix is not None else (None, None)
    category = _descendant_text(current_fix, 'category') if current_fix is not None else None
    classification = 'Tropical Cyclone'
    if category:
        classification = f'{classification} (Category {category})'

    geometries: dict[str, Geometry] = {}
    for tag, key in (
        ('tcTrack', 'forecast_track'),
        ('tcWarningArea', 'warning_area'),
        ('tcWatchArea', 'watch_area'),
        ('tcForecastArea', 'forecast_area'),
        ('tcWindArea', 'wind_area'),
    ):
        geometry = _geometry_for_elements(
            root,
            tag,
            line=tag == 'tcTrack',
            track_type='Forecast' if tag == 'tcTrack' else None,
        )
        if geometry is not None:
            geometries[key] = geometry

    parameters: dict[str, list[str]] = {}
    product_id = _descendant_text(root, 'identifier') or _product_id_from_url(url)
    if product_id:
        parameters['BoM Product ID'] = [product_id]
    forecast_time = _descendant_text(root, 'fcastTime')
    if forecast_time:
        parameters['BoM Forecast Time'] = [forecast_time]
    expiry_hours = _descendant_text(root, 'expiryHrs')
    if expiry_hours:
        parameters['BoM Expiry Hours'] = [expiry_hours]
    if category:
        parameters['BoM Current Category'] = [category]

    return TropicalSystem(
        id=disturbance_id,
        source=source,
        classification=classification,
        name=name,
        headline=f'Tropical Cyclone {name}',
        basin='Australian Region',
        url=url,
        issued_at=WarningBackend.parse_datetime(_descendant_text(root, 'issueTime')),
        center_lat=center_lat,
        center_lon=center_lon,
        summary=f'Bureau of Meteorology tropical cyclone track product for {name}.',
        data_urls={'forecast_track_map': url},
        geometries=geometries,
        parameters=parameters,
    )


def _current_fix(root: ElementTree.Element) -> ElementTree.Element | None:
    fallback: ElementTree.Element | None = None
    for node in root.iter():
        if local_name(node.tag) != 'tcFix':
            continue
        fallback = fallback or node
        if (_descendant_text(node, 'fixType') or '').casefold() == 'current':
            return node
    return fallback


def _geometry_for_elements(
    root: ElementTree.Element,
    tag: str,
    *,
    line: bool,
    track_type: str | None,
) -> Geometry | None:
    positions: list[list[list[float]]] = []
    for element in root.iter():
        if local_name(element.tag) != tag:
            continue
        if track_type and (_descendant_text(element, 'trackType') or '').casefold() != track_type.casefold():
            continue
        for coordinate_node in element.iter():
            if local_name(coordinate_node.tag) != 'coordinates':
                continue
            coordinates = _coordinates(''.join(coordinate_node.itertext()))
            if len(coordinates) >= (2 if line else 3):
                positions.append(coordinates)

    if not positions:
        return None
    if line:
        return {
            'type': 'LineString' if len(positions) == 1 else 'MultiLineString',
            'coordinates': positions[0] if len(positions) == 1 else positions,
        }

    polygons = []
    for ring in positions:
        if ring[0] != ring[-1]:
            ring = [*ring, ring[0]]
        polygons.append([ring])
    return {
        'type': 'Polygon' if len(polygons) == 1 else 'MultiPolygon',
        'coordinates': polygons[0] if len(polygons) == 1 else polygons,
    }


def _point_coordinates(element: ElementTree.Element) -> tuple[float | None, float | None]:
    coordinate_text = _descendant_text(element, 'coordinates')
    coordinates = _coordinates(coordinate_text or '')
    if not coordinates:
        return None, None
    lon, lat = coordinates[0]
    return lat, lon


def _coordinates(value: str) -> list[list[float]]:
    coordinates: list[list[float]] = []
    for position in value.split():
        parts = position.split(',')
        if len(parts) < 2:
            continue
        try:
            coordinates.append([float(parts[0]), float(parts[1])])
        except ValueError:
            continue
    return coordinates


def _product_id_from_url(url: str) -> str | None:
    match = _LISTING_FILENAME_RE.search(url)
    if match is None:
        return None
    return match.group(1).rsplit('.', 1)[0].upper()


def _descendant_text(element: ElementTree.Element | None, name: str) -> str | None:
    if element is None:
        return None
    for node in element.iter():
        if local_name(node.tag) != name:
            continue
        text = ''.join(node.itertext()).strip()
        return text or None
    return None


def _prefer_system(candidate: TropicalSystem, previous: TropicalSystem) -> bool:
    candidate_time = candidate.issued_at
    previous_time = previous.issued_at
    if candidate_time is not None and previous_time is not None and candidate_time != previous_time:
        return candidate_time > previous_time
    if candidate_time is not None and previous_time is None:
        return True
    if candidate_time is None and previous_time is not None:
        return False
    return (candidate.url or '') > (previous.url or '')
