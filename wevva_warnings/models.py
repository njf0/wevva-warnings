"""Normalized weather alert model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .sources import DisplayGeography, WarningSource

Geometry = dict[str, Any]
Geocodes = dict[str, list[str]]
Parameters = dict[str, list[str]]
_LEADING_BLANK_LINES_RE = re.compile(r'\A(?:[ \t]*(?:\r\n|\r|\n))+')


def _extract_geometry_positions(geometry: Geometry | None) -> list[tuple[float, float]]:
    """Return all ``(lon, lat)`` positions from a supported geometry."""
    if geometry is None:
        return []

    geometry_type = str(geometry.get('type') or 'Unknown')
    coordinates = geometry.get('coordinates') or []

    if geometry_type == 'Point' and isinstance(coordinates, list) and len(coordinates) >= 2:
        lon, lat = coordinates[:2]
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            return [(float(lon), float(lat))]
        return []

    if geometry_type in {'LineString', 'MultiPoint'}:
        positions: list[tuple[float, float]] = []
        for point in coordinates:
            if (
                isinstance(point, list)
                and len(point) >= 2
                and isinstance(point[0], (int, float))
                and isinstance(point[1], (int, float))
            ):
                positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'Polygon':
        positions = []
        for ring in coordinates:
            for point in ring:
                if (
                    isinstance(point, list)
                    and len(point) >= 2
                    and isinstance(point[0], (int, float))
                    and isinstance(point[1], (int, float))
                ):
                    positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'MultiLineString':
        positions = []
        for line in coordinates:
            for point in line:
                if (
                    isinstance(point, list)
                    and len(point) >= 2
                    and isinstance(point[0], (int, float))
                    and isinstance(point[1], (int, float))
                ):
                    positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'MultiPolygon':
        positions = []
        for polygon in coordinates:
            for ring in polygon:
                for point in ring:
                    if (
                        isinstance(point, list)
                        and len(point) >= 2
                        and isinstance(point[0], (int, float))
                        and isinstance(point[1], (int, float))
                    ):
                        positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'GeometryCollection':
        positions = []
        for child in geometry.get('geometries') or []:
            if isinstance(child, dict):
                positions.extend(_extract_geometry_positions(child))
        return positions

    return []


def _summarize_geometry(geometry: Geometry | None) -> dict[str, object] | None:
    """Return a compact summary of one geometry.

    Parameters
    ----------
    geometry : Geometry | None
        Geometry to summarize.

    Returns
    -------
    dict[str, object] | None
        Compact geometry summary, or ``None`` if no geometry is present.

    """
    if geometry is None:
        return None

    geometry_type = str(geometry.get('type') or 'Unknown')
    coordinates = geometry.get('coordinates') or []
    summary: dict[str, object] = {'type': geometry_type}

    if geometry_type == 'Point':
        summary['points'] = 1
    elif geometry_type == 'LineString':
        summary['points'] = len(coordinates)
    elif geometry_type == 'MultiPoint':
        summary['points'] = len(coordinates)
    elif geometry_type == 'Polygon':
        summary['rings'] = len(coordinates)
    elif geometry_type == 'MultiLineString':
        summary['lines'] = len(coordinates)
        summary['points'] = sum(len(line) for line in coordinates)
    elif geometry_type == 'MultiPolygon':
        summary['polygons'] = len(coordinates)
        summary['rings'] = sum(len(polygon) for polygon in coordinates)
    elif geometry_type == 'GeometryCollection':
        summary['geometries'] = len(geometry.get('geometries') or [])

    positions = _extract_geometry_positions(geometry)
    if positions:
        longitudes = [position[0] for position in positions]
        latitudes = [position[1] for position in positions]
        summary['points'] = len(positions)
        summary['bbox'] = [
            round(min(longitudes), 3),
            round(min(latitudes), 3),
            round(max(longitudes), 3),
            round(max(latitudes), 3),
        ]

    return summary


def _summarize_geometries(geometries: dict[str, Geometry]) -> dict[str, dict[str, object]]:
    """Return compact summaries for a geometry mapping."""
    summary: dict[str, dict[str, object]] = {}
    for key, geometry in geometries.items():
        compact = _summarize_geometry(geometry)
        if compact is not None:
            summary[key] = compact
    return summary


def _summarize_source_info(source_info: WarningSource | None) -> dict[str, object] | None:
    """Return compact source metadata for Rich output."""
    if source_info is None:
        return None
    display_geography = getattr(source_info, 'display_geography', None)
    return {
        'id': getattr(source_info, 'id', None),
        'name': getattr(source_info, 'name', None),
        'country_code': getattr(source_info, 'country_code', None),
        'issuer_country_code': getattr(source_info, 'issuer_country_code', None),
        'display_geography': (
            {
                'kind': display_geography.kind,
                'code': display_geography.code,
                'name': display_geography.name,
            }
            if display_geography is not None
            else None
        ),
        'lang': getattr(source_info, 'lang', None),
        'kind': getattr(source_info, 'kind', None),
    }


@dataclass(slots=True)
class Alert:
    """Represent one normalized weather alert."""

    id: str
    source: str
    event: str
    headline: str
    url: str | None = None
    severity: str | None = None
    urgency: str | None = None
    certainty: str | None = None
    description: str | None = None
    instruction: str | None = None
    onset: datetime | None = None
    expires: datetime | None = None
    area_names: list[str] = field(default_factory=list)
    geocodes: Geocodes = field(default_factory=dict)
    parameters: Parameters = field(default_factory=dict)
    geometry: Geometry | None = None
    source_info: WarningSource | None = field(default=None, repr=False)

    def __rich_repr__(self) -> object:
        """Yield compact Rich pretty-print fields.

        Returns
        -------
        object
            Iterator-compatible Rich repr payload.

        """
        yield 'id', self.id
        yield 'source', self.source
        yield 'source_info', _summarize_source_info(self.source_info), None
        yield 'event', self.event
        yield 'headline', self.headline
        yield 'url', self.url, None
        yield 'severity', self.severity, None
        yield 'urgency', self.urgency, None
        yield 'certainty', self.certainty, None
        yield 'description', self.description, None
        yield 'instruction', self.instruction, None
        yield 'onset', self.onset.isoformat() if self.onset else None, None
        yield 'expires', self.expires.isoformat() if self.expires else None, None
        yield 'area_names', self.area_names, []
        yield 'geocodes', self.geocodes, {}
        yield 'parameters', self.parameters, {}
        yield 'geometry', _summarize_geometry(self.geometry), None

    def is_active(self, now: datetime | None = None) -> bool:
        """Return whether the alert is currently active.

        Parameters
        ----------
        now : datetime | None, optional
            Time to compare the alert against. If not provided, the current UTC
            time will be used.

        Returns
        -------
        bool
            ``True`` if the alert has started and has not yet expired,
            otherwise ``False``.

        """
        if now is None:
            now = datetime.now(UTC)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        else:
            now = now.astimezone(UTC)

        onset = self.onset
        if onset is not None:
            if onset.tzinfo is None:
                onset = onset.replace(tzinfo=UTC)
            else:
                onset = onset.astimezone(UTC)
            if now < onset:
                return False

        expires = self.expires
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            else:
                expires = expires.astimezone(UTC)
            if now > expires:
                return False

        return True


@dataclass(slots=True)
class TropicalSystem:
    """Represent one normalized tropical cyclone system."""

    id: str
    source: str
    classification: str
    name: str
    headline: str
    basin: str | None = None
    url: str | None = None
    issued_at: datetime | None = None
    advisory_number: str | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    movement: str | None = None
    min_pressure: str | None = None
    max_wind: str | None = None
    summary: str | None = None
    data_urls: dict[str, str] = field(default_factory=dict)
    geometries: dict[str, Geometry] = field(default_factory=dict)
    parameters: Parameters = field(default_factory=dict)
    source_info: WarningSource | None = field(default=None, repr=False)

    @property
    def display_geography(self) -> DisplayGeography | None:
        """Return basin, source, or issuer-country map context in precedence order."""
        if self.source_info is None:
            return None
        return self.source_info.resolve_display_geography(self.basin)

    def __rich_repr__(self) -> object:
        """Yield compact Rich pretty-print fields."""
        yield 'id', self.id
        yield 'source', self.source
        yield 'source_info', _summarize_source_info(self.source_info), None
        yield 'display_geography', self.display_geography, None
        yield 'classification', self.classification
        yield 'name', self.name
        yield 'headline', self.headline
        yield 'basin', self.basin, None
        yield 'url', self.url, None
        yield 'issued_at', self.issued_at.isoformat() if self.issued_at else None, None
        yield 'advisory_number', self.advisory_number, None
        yield 'center_lat', self.center_lat, None
        yield 'center_lon', self.center_lon, None
        yield 'movement', self.movement, None
        yield 'min_pressure', self.min_pressure, None
        yield 'max_wind', self.max_wind, None
        yield 'summary', self.summary, None
        yield 'data_urls', self.data_urls, {}
        yield 'geometries', _summarize_geometries(self.geometries), {}
        yield 'parameters', self.parameters, {}


@dataclass(slots=True)
class TropicalProduct:
    """Represent optional source-specific detail for one tropical system.

    ``kind`` is a small semantic rendering category while ``label`` preserves
    the issuing provider's terminology. Text content defaults to safely
    normalized Markdown, while providers may retain ``plain`` for products
    whose fixed layout renders poorly as Markdown. ``data`` is an optional,
    deliberately provider-specific structured payload.
    """

    kind: str
    label: str
    title: str | None = None
    issued_at: datetime | None = None
    content: str | None = None
    content_format: Literal['markdown', 'plain'] = 'markdown'
    url: str | None = None
    data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Remove leading blank lines without changing first-line Markdown."""
        if self.content is not None:
            self.content = _LEADING_BLANK_LINES_RE.sub('', self.content)

    def __rich_repr__(self) -> object:
        """Yield compact Rich pretty-print fields."""
        yield 'kind', self.kind
        yield 'label', self.label
        yield 'title', self.title, None
        yield 'issued_at', self.issued_at.isoformat() if self.issued_at else None, None
        yield 'content', self.content, None
        yield 'content_format', self.content_format, None
        yield 'url', self.url, None
        yield 'data', self.data, None


@dataclass(slots=True)
class CanonicalTropicalSystem:
    """Group source observations that share one explicit storm name.

    The wrapper expresses identity only.  Meteorological facts remain on the
    ordered, source-specific :class:`TropicalSystem` observations.
    """

    name: str
    observations: list[TropicalSystem] = field(default_factory=list)

    def __rich_repr__(self) -> object:
        """Yield compact Rich pretty-print fields."""
        yield 'name', self.name
        yield 'observations', self.observations
