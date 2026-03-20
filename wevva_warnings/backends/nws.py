"""U.S. National Weather Service backend."""

from __future__ import annotations

from typing import Any

from .base import BackendError, WarningBackend, fetch_json
from ..models import Alert
from ..sources import WarningSource


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
            areas=self.split_areas(properties.get('areaDesc')),
            geometry=geometry,
        )
