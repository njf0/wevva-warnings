"""Minimal GeoJSON geometry helpers for alert matching."""

from __future__ import annotations

from typing import Any


def point_in_geometry(lat: float, lon: float, geometry: dict[str, Any]) -> bool:
    """Return whether a point lies inside a supported GeoJSON geometry.

    Parameters
    ----------
    lat : float
        Latitude of the point to test.
    lon : float
        Longitude of the point to test.
    geometry : dict[str, Any]
        GeoJSON geometry mapping. Coordinates are assumed to be in the usual
        GeoJSON ``lon, lat`` order.

    Returns
    -------
    bool
        ``True`` if the point lies inside the geometry, otherwise ``False``.

    """
    if not _point_in_bbox(lat, lon, geometry.get('bbox')):
        return False

    geometry_type = geometry.get('type')
    coordinates = geometry.get('coordinates')

    if geometry_type == 'Polygon':
        return _point_in_polygon(lat, lon, coordinates)
    if geometry_type == 'MultiPolygon' and isinstance(coordinates, list):
        return any(_point_in_polygon(lat, lon, polygon) for polygon in coordinates)
    return False


def _point_in_bbox(lat: float, lon: float, bbox: Any) -> bool:
    """Return whether a point lies inside a [min_lon, min_lat, max_lon, max_lat] bbox."""
    if not isinstance(bbox, list) or len(bbox) != 4:
        return True
    min_lon, min_lat, max_lon, max_lat = bbox
    if not all(isinstance(value, (int, float)) for value in (min_lon, min_lat, max_lon, max_lat)):
        return True
    return float(min_lon) <= lon <= float(max_lon) and float(min_lat) <= lat <= float(max_lat)


def _point_in_polygon(lat: float, lon: float, polygon: Any) -> bool:
    """Return whether a point lies inside a polygon.

    Parameters
    ----------
    lat : float
        Latitude of the point to test.
    lon : float
        Longitude of the point to test.
    polygon : Any
        GeoJSON polygon coordinate structure consisting of an outer ring and
        optional interior holes.

    Returns
    -------
    bool
        ``True`` if the point lies inside the outer ring and outside all holes,
        otherwise ``False``.

    """
    if not isinstance(polygon, list) or not polygon:
        return False
    outer_ring = polygon[0]
    if not _point_in_ring(lat, lon, outer_ring):
        return False
    return all(not _point_in_ring(lat, lon, hole) for hole in polygon[1:])


def _point_in_ring(lat: float, lon: float, ring: Any) -> bool:
    """Return whether a point lies inside one linear ring.

    Parameters
    ----------
    lat : float
        Latitude of the point to test.
    lon : float
        Longitude of the point to test.
    ring : Any
        GeoJSON linear ring coordinate list.

    Returns
    -------
    bool
        ``True`` if the point lies inside the ring or on its boundary,
        otherwise ``False``.

    """
    if not isinstance(ring, list) or len(ring) < 3:
        return False

    points: list[tuple[float, float]] = []
    for point in ring:
        if (
            isinstance(point, list)
            and len(point) >= 2
            and isinstance(point[0], (int, float))
            and isinstance(point[1], (int, float))
        ):
            # GeoJSON positions are [lon, lat].
            points.append((float(point[0]), float(point[1])))
    if len(points) < 3:
        return False

    if points[0] != points[-1]:
        points.append(points[0])

    inside = False
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]

        if _point_on_segment(lon, lat, x1, y1, x2, y2):
            return True

        crosses = (y1 > lat) != (y2 > lat)
        if not crosses:
            continue

        intersect_lon = ((x2 - x1) * (lat - y1) / (y2 - y1)) + x1
        if lon < intersect_lon:
            inside = not inside
    return inside


def _point_on_segment(
    point_x: float,
    point_y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    epsilon: float = 1e-12,
) -> bool:
    """Return whether a point lies on a line segment.

    Parameters
    ----------
    point_x : float
        X coordinate of the point to test.
    point_y : float
        Y coordinate of the point to test.
    x1 : float
        X coordinate of the first segment endpoint.
    y1 : float
        Y coordinate of the first segment endpoint.
    x2 : float
        X coordinate of the second segment endpoint.
    y2 : float
        Y coordinate of the second segment endpoint.
    epsilon : float, optional
        Numerical tolerance used when comparing floating-point values.

    Returns
    -------
    bool
        ``True`` if the point lies on the segment, otherwise ``False``.

    """
    cross = (point_y - y1) * (x2 - x1) - (point_x - x1) * (y2 - y1)
    if abs(cross) > epsilon:
        return False

    min_x = min(x1, x2) - epsilon
    max_x = max(x1, x2) + epsilon
    min_y = min(y1, y2) - epsilon
    max_y = max(y1, y2) + epsilon
    return min_x <= point_x <= max_x and min_y <= point_y <= max_y
