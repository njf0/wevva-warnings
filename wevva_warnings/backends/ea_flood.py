"""Provider backend for Environment Agency flood warnings."""

from __future__ import annotations

from typing import Any

from ..geometry import point_in_geometry
from ..models import Alert
from ..sources import WarningSource
from .base import BackendError, WarningBackend, fetch_json


class EAFloodBackend(WarningBackend):
    """Fetch flood warnings from the Environment Agency flood API."""

    backend_id = 'ea_flood'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for an Environment Agency flood source.

        Parameters
        ----------
        source : WarningSource
            Source definition to query.
        lat : float | None, optional
            Latitude used for optional exact point filtering.
        lon : float | None, optional
            Longitude used for optional exact point filtering.
        lang : str | None, optional
            Unused for this backend. Included for interface compatibility.
        debug : bool, optional
            If True, log fetch failures.

        Returns
        -------
        list[Alert]
            Alerts returned by the Environment Agency API.

        """
        del lang
        if not source.url:
            return []

        try:
            payload = fetch_json(source.url, debug=debug)
        except BackendError:
            return []
        items = payload.get('items')
        if not isinstance(items, list):
            return []

        alerts: list[Alert] = []
        for item in items:
            alert = self._to_alert(source, item, lat=lat, lon=lon, debug=debug)
            if alert is not None:
                alerts.append(alert)
        return alerts

    def _to_alert(
        self,
        source: WarningSource,
        item: Any,
        *,
        lat: float | None,
        lon: float | None,
        debug: bool,
    ) -> Alert | None:
        """Convert one Environment Agency warning object into an alert."""
        if not isinstance(item, dict):
            return None

        area = item.get('floodArea')
        if not isinstance(area, dict):
            area = {}

        geometry = self._fetch_polygon_geometry(area.get('polygon'), debug=debug)
        if lat is not None and lon is not None:
            if geometry is None or not point_in_geometry(lat, lon, geometry):
                return None

        event = self.text_or_none(item.get('severity')) or 'Flood warning'
        headline = self.text_or_none(item.get('description')) or event
        identifier = (
            self.text_or_none(item.get('floodAreaID'))
            or self.text_or_none(item.get('@id'))
            or headline
        )

        area_names = _unique_texts(
            self.text_or_none(area.get('label')),
            self.text_or_none(area.get('description')),
            self.text_or_none(area.get('county')),
        )

        geocodes: dict[str, list[str]] = {}
        flood_area_id = self.text_or_none(item.get('floodAreaID')) or self.text_or_none(area.get('notation'))
        if flood_area_id:
            geocodes['EA Flood Area ID'] = [flood_area_id]

        parameters: dict[str, list[str]] = {}
        severity = self.text_or_none(item.get('severity'))
        if severity:
            parameters['EA Severity'] = [severity]
        severity_level = item.get('severityLevel')
        if severity_level is not None:
            parameters['EA Severity Level'] = [str(severity_level)]
        river_or_sea = self.text_or_none(area.get('riverOrSea'))
        if river_or_sea:
            parameters['EA River Or Sea'] = [river_or_sea]

        return Alert(
            id=identifier,
            source=source.id,
            event=event,
            headline=headline,
            url=self.text_or_none(item.get('@id')),
            severity='Unknown',
            urgency='Unknown',
            certainty='Unknown',
            description=self.text_or_none(item.get('message')) or headline,
            onset=self.parse_datetime(item.get('timeRaised')),
            expires=None,
            area_names=area_names,
            geocodes=geocodes,
            parameters=parameters,
            geometry=geometry,
        )

    def _fetch_polygon_geometry(self, polygon_url: Any, *, debug: bool) -> dict[str, Any] | None:
        """Fetch and extract polygon geometry from one flood-area URL."""
        url = self.text_or_none(polygon_url)
        if not url:
            return None

        try:
            payload = fetch_json(url, debug=debug)
        except BackendError:
            return None
        features = payload.get('features')
        if not isinstance(features, list) or not features:
            return None

        feature = features[0]
        if not isinstance(feature, dict):
            return None

        geometry = feature.get('geometry')
        if not isinstance(geometry, dict):
            return None

        return geometry


def _unique_texts(*values: str | None) -> list[str]:
    """Return unique non-empty strings preserving order."""
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
