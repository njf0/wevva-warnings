"""Small CAP parser for normalized alert fields."""

from __future__ import annotations

import re
from datetime import datetime
from math import asin, atan2, cos, degrees, pi, radians, sin
from typing import Any
from xml.etree import ElementTree

from .models import Alert, Geocodes, Parameters

EARTH_RADIUS_KM = 6371.0088
CIRCLE_SEGMENTS = 36


def parse_cap_alert(
    xml_payload: str | bytes,
    *,
    source: str = 'cap',
    preferred_lang: str | None = None,
    url: str | None = None,
) -> Alert | None:
    """Parse one CAP alert document into a normalized alert.

    Parameters
    ----------
    xml_payload : str | bytes
        CAP XML document to parse.
    source : str, optional
        Source identifier to attach to the returned alert.
    preferred_lang : str | None, optional
        Preferred language code used when selecting a CAP ``info`` block.
    url : str | None, optional
        Canonical URL for the CAP document, if known.

    Returns
    -------
    Alert | None
        A normalized alert if parsing succeeds, otherwise ``None``.

    """
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return None

    if _local_name(root.tag) != 'alert':
        root = next(
            (node for node in root.iter() if isinstance(node.tag, str) and _local_name(node.tag) == 'alert'),
            None,
        )
        if root is None:
            return None

    identifier = _child_text(root, 'identifier') or ''
    info = _select_info_block(root, preferred_lang=preferred_lang)
    if info is None:
        return None

    event = _child_text(info, 'event') or 'Weather Alert'
    headline = _child_text(info, 'headline') or event

    area_names, geocodes, geometry = _extract_area_metadata(info)
    parameters = _collect_named_values(info, 'parameter')
    onset = _child_text(info, 'onset') or _child_text(info, 'effective')
    return Alert(
        id=identifier or headline,
        source=source,
        event=event,
        headline=headline,
        url=url,
        severity=_child_text(info, 'severity'),
        urgency=_child_text(info, 'urgency'),
        certainty=_child_text(info, 'certainty'),
        description=_child_text(info, 'description'),
        instruction=_child_text(info, 'instruction'),
        onset=parse_cap_datetime(onset),
        expires=parse_cap_datetime(_child_text(info, 'expires')),
        area_names=area_names,
        geocodes=geocodes,
        parameters=parameters,
        geometry=geometry,
    )


def parse_cap_datetime(value: str | None) -> datetime | None:
    """Parse a CAP date/time string.

    Parameters
    ----------
    value : str | None
        CAP date/time string to parse.

    Returns
    -------
    datetime | None
        Parsed datetime if successful, otherwise ``None``.

    """
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = f'{text[:-1]}+00:00'

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _select_info_block(
    alert: ElementTree.Element,
    preferred_lang: str | None = None,
) -> ElementTree.Element | None:
    """Select the most appropriate CAP ``info`` block.

    Parameters
    ----------
    alert : ElementTree.Element
        CAP ``alert`` element.
    preferred_lang : str | None, optional
        Preferred language code to match against ``info/language`` values.

    Returns
    -------
    ElementTree.Element | None
        The selected ``info`` element, or ``None`` if the alert does not
        contain any ``info`` blocks.

    """
    infos = [child for child in alert if _local_name(child.tag) == 'info']
    if not infos:
        return None

    preferred = _normalize_language_tag(preferred_lang)
    if preferred:
        match = next(
            (info for info in infos if _normalize_language_tag(_child_text(info, 'language')) == preferred),
            None,
        )
        if match is not None:
            return match

    return next(
        (info for info in infos if _normalize_language_tag(_child_text(info, 'language')) == 'en'),
        infos[0],
    )


def _normalize_language_tag(value: str | None) -> str:
    """Normalize a language tag to its base language code.

    Parameters
    ----------
    value : str | None
        Language tag to normalize.

    Returns
    -------
    str
        Lowercase base language code such as ``en`` or ``fr``. Returns an
        empty string for missing input.

    """
    text = (value or '').split(',', 1)[0].strip().lower()
    return text.split('-', 1)[0].split('_', 1)[0]


def _extract_area_metadata(
    info: ElementTree.Element,
) -> tuple[list[str], Geocodes, dict[str, Any] | None]:
    """Extract flattened area metadata from a CAP ``info`` block.

    Parameters
    ----------
    info : ElementTree.Element
        CAP ``info`` element to inspect.

    Returns
    -------
    tuple[list[str], Geocodes, dict[str, Any] | None]
        Flat area names, grouped geocodes, and combined alert geometry.

    """
    area_names: list[str] = []
    geocodes: Geocodes = {}
    geometries: list[dict[str, Any]] = []
    for area in [child for child in info if _local_name(child.tag) == 'area']:
        description = _child_text(area, 'areaDesc')
        if description:
            normalized = description.replace(';', ',')
            for part in (item.strip() for item in normalized.split(',')):
                if part and part not in area_names:
                    area_names.append(part)

        rings: list[list[list[float]]] = []
        for child in area:
            tag_name = _local_name(child.tag)
            if tag_name == 'polygon':
                ring = _parse_cap_polygon((child.text or '').strip())
            elif tag_name == 'circle':
                ring = _parse_cap_circle((child.text or '').strip())
            elif tag_name == 'geocode':
                geocode = _parse_geocode(child)
                if geocode is not None:
                    values = geocodes.setdefault(geocode[0], [])
                    if geocode[1] not in values:
                        values.append(geocode[1])
                continue
            else:
                continue
            if ring:
                rings.append(ring)
        geometry = _rings_to_geometry(rings)
        if geometry is not None:
            geometries.append(geometry)

    return area_names, geocodes, _combined_geometries(geometries)


def _combined_geometries(geometries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Combine area geometries into one alert-level geometry.

    Parameters
    ----------
    geometries : list[dict[str, Any]]
        Per-area geometries to combine.

    Returns
    -------
    dict[str, Any] | None
        Combined GeoJSON ``Polygon`` or ``MultiPolygon`` geometry, or
        ``None`` if no geometries are present.

    """
    polygons: list[list[list[list[float]]]] = []
    for geometry in geometries:
        coordinates = geometry.get('coordinates')
        if geometry.get('type') == 'Polygon' and isinstance(coordinates, list):
            polygons.append(coordinates)
        elif geometry.get('type') == 'MultiPolygon' and isinstance(coordinates, list):
            polygons.extend(polygon for polygon in coordinates if isinstance(polygon, list))

    if not polygons:
        return None
    if len(polygons) == 1:
        return {'type': 'Polygon', 'coordinates': polygons[0]}
    return {'type': 'MultiPolygon', 'coordinates': polygons}


def _parse_geocode(element: ElementTree.Element) -> tuple[str, str] | None:
    """Parse one CAP ``geocode`` element.

    Parameters
    ----------
    element : ElementTree.Element
        CAP ``geocode`` element to parse.

    Returns
    -------
    tuple[str, str] | None
        Parsed ``(valueName, value)`` pair if the element contains both
        fields, otherwise ``None``.

    """
    value_name = _child_text(element, 'valueName')
    value = _child_text(element, 'value')
    if value_name is None or value is None:
        return None
    return value_name, value


def _collect_named_values(element: ElementTree.Element, name: str) -> Parameters:
    """Collect repeated CAP name/value elements into grouped mappings.

    Parameters
    ----------
    element : ElementTree.Element
        Parent XML element to inspect.
    name : str
        Local tag name of child elements containing ``valueName`` and
        ``value`` children.

    Returns
    -------
    Parameters
        Mapping of ``valueName`` to all associated values.

    """
    values: Parameters = {}
    for child in element:
        if _local_name(child.tag) != name:
            continue
        pair = _parse_geocode(child)
        if pair is None:
            continue
        bucket = values.setdefault(pair[0], [])
        if pair[1] not in bucket:
            bucket.append(pair[1])
    return values


def _parse_cap_polygon(text: str) -> list[list[float]] | None:
    """Parse CAP polygon text into a GeoJSON-style ring.

    Parameters
    ----------
    text : str
        CAP polygon text containing ``lat,lon`` pairs.

    Returns
    -------
    list[list[float]] | None
        Closed GeoJSON-style ring in ``lon, lat`` order, or ``None`` if the
        text cannot be parsed into a valid polygon.

    """
    if not text:
        return None

    if text.lstrip().startswith('['):
        ring = _parse_bracketed_polygon(text)
        if ring:
            return ring

    ring: list[list[float]] = []
    for pair in text.split():
        parts = pair.split(',', maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        except ValueError:
            continue
        ring.append([lon, lat])

    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def _parse_cap_circle(text: str) -> list[list[float]] | None:
    """Parse CAP circle text into a polygon ring approximation.

    Parameters
    ----------
    text : str
        CAP circle text in ``lat,lon radius_km`` form.

    Returns
    -------
    list[list[float]] | None
        Closed GeoJSON-style ring approximating the circle, or ``None`` if the
        text cannot be parsed.

    """
    if not text:
        return None

    parts = text.split()
    if len(parts) != 2:
        return None

    center_parts = parts[0].split(',', maxsplit=1)
    if len(center_parts) != 2:
        return None

    try:
        lat = float(center_parts[0].strip())
        lon = float(center_parts[1].strip())
        radius_km = float(parts[1].strip())
    except ValueError:
        return None

    if radius_km <= 0:
        return None

    return _circle_to_ring(lat, lon, radius_km)


def _circle_to_ring(lat: float, lon: float, radius_km: float) -> list[list[float]]:
    """Approximate a CAP circle as a closed GeoJSON ring.

    Parameters
    ----------
    lat : float
        Latitude of the circle centre.
    lon : float
        Longitude of the circle centre.
    radius_km : float
        Circle radius in kilometres.

    Returns
    -------
    list[list[float]]
        Closed GeoJSON-style ring approximating the circle.

    """
    lat_radians = radians(lat)
    lon_radians = radians(lon)
    angular_distance = radius_km / EARTH_RADIUS_KM

    ring: list[list[float]] = []
    for index in range(CIRCLE_SEGMENTS):
        bearing = 2 * pi * index / CIRCLE_SEGMENTS
        sin_lat = sin(lat_radians)
        cos_lat = cos(lat_radians)
        sin_distance = sin(angular_distance)
        cos_distance = cos(angular_distance)

        projected_lat = sin_lat * cos_distance + cos_lat * sin_distance * cos(bearing)
        projected_lat = max(-1.0, min(1.0, projected_lat))
        point_lat = asin(projected_lat)
        point_lon = lon_radians + atan2(
            sin(bearing) * sin_distance * cos_lat,
            cos_distance - sin_lat * sin(point_lat),
        )

        ring.append([_normalize_longitude(degrees(point_lon)), degrees(point_lat)])

    ring.append(ring[0])
    return ring


def _normalize_longitude(value: float) -> float:
    """Normalize a longitude into the ``[-180, 180)`` range.

    Parameters
    ----------
    value : float
        Longitude value to normalize.

    Returns
    -------
    float
        Normalized longitude.

    """
    return ((value + 180.0) % 360.0) - 180.0


def _parse_bracketed_polygon(text: str) -> list[list[float]] | None:
    """Parse bracketed ``[lat, lon]`` polygon text into a ring.

    Parameters
    ----------
    text : str
        Polygon text containing bracketed latitude and longitude pairs.

    Returns
    -------
    list[list[float]] | None
        Closed GeoJSON-style ring in ``lon, lat`` order, or ``None`` if the
        text cannot be parsed into a valid polygon.

    """
    ring: list[list[float]] = []
    for lat_text, lon_text in re.findall(
        r'\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]',
        text,
    ):
        ring.append([float(lon_text), float(lat_text)])

    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def _rings_to_geometry(rings: list[list[list[float]]]) -> dict[str, Any] | None:
    """Convert parsed rings into a GeoJSON geometry mapping.

    Parameters
    ----------
    rings : list[list[list[float]]]
        Parsed polygon rings in GeoJSON coordinate order.

    Returns
    -------
    dict[str, Any] | None
        GeoJSON ``Polygon`` or ``MultiPolygon`` geometry, or ``None`` if no
        rings were supplied.

    """
    if not rings:
        return None
    if len(rings) == 1:
        return {'type': 'Polygon', 'coordinates': [rings[0]]}
    return {'type': 'MultiPolygon', 'coordinates': [[ring] for ring in rings]}


def _child_text(element: ElementTree.Element, name: str) -> str | None:
    """Return the trimmed text of a named child element.

    Parameters
    ----------
    element : ElementTree.Element
        Parent XML element to search.
    name : str
        Local child tag name to match.

    Returns
    -------
    str | None
        Trimmed child text if present, otherwise ``None``.

    """
    for child in element:
        if _local_name(child.tag) != name:
            continue
        value = (child.text or '').strip()
        if value:
            return value
    return None


def _local_name(tag: str) -> str:
    """Return the local name for a possibly namespaced XML tag.

    Parameters
    ----------
    tag : str
        XML tag, optionally in ``{namespace}name`` form.

    Returns
    -------
    str
        Tag name without any namespace prefix.

    """
    return tag.split('}')[-1]
