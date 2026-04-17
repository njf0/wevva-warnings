"""Normalized weather alert model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

Geometry = dict[str, Any]
Geocodes = dict[str, list[str]]
Parameters = dict[str, list[str]]


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

    positions: list[tuple[float, float]] = []
    if geometry_type == 'Polygon':
        summary['rings'] = len(coordinates)
        for ring in coordinates:
            for lon, lat in ring:
                positions.append((float(lon), float(lat)))
    elif geometry_type == 'MultiPolygon':
        summary['polygons'] = len(coordinates)
        summary['rings'] = sum(len(polygon) for polygon in coordinates)
        for polygon in coordinates:
            for ring in polygon:
                for lon, lat in ring:
                    positions.append((float(lon), float(lat)))

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

    def __rich_repr__(self) -> object:
        """Yield compact Rich pretty-print fields.

        Returns
        -------
        object
            Iterator-compatible Rich repr payload.

        """
        yield 'id', self.id
        yield 'source', self.source
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
