"""Environment Canada GeoMet backend."""

from __future__ import annotations

from typing import Any

from ..geometry import point_in_geometry
from ..models import Alert
from ..sources import WarningSource
from .base import BackendError, WarningBackend, fetch_json


class GeoMetBackend(WarningBackend):
    """Fetch alerts from the official GeoMet API."""

    backend_id = 'geomet'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a GeoMet source.

        Parameters
        ----------
        source : WarningSource
            Source definition to query.
        lat : float | None, optional
            Latitude used to constrain the query bounding box.
        lon : float | None, optional
            Longitude used to constrain the query bounding box.
        lang : str | None, optional
            Preferred language code for localized fields.
        debug : bool, optional
            If True, log fetch failures.

        Returns
        -------
        list[Alert]
            Alerts returned by the GeoMet API for the requested source.

        """
        if not source.url:
            return []

        preferred_lang = self._normalize_lang(lang or source.lang)
        params = {
            'f': 'json',
            'lang': preferred_lang,
            'limit': 500,
        }
        if lat is not None and lon is not None:
            delta = 1.0
            west = lon - delta
            south = lat - delta
            east = lon + delta
            north = lat + delta
            params['bbox'] = f'{west:.4f},{south:.4f},{east:.4f},{north:.4f}'

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
            alert = self._to_alert(source, feature, lat=lat, lon=lon, lang=preferred_lang)
            if alert is not None:
                alerts.append(alert)
        return alerts

    def _to_alert(
        self,
        source: WarningSource,
        feature: Any,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str = 'en',
    ) -> Alert | None:
        """Convert one GeoMet feature into a normalized alert.

        Parameters
        ----------
        source : WarningSource
            Source definition the feature came from.
        feature : Any
            GeoJSON feature to convert.
        lat : float | None, optional
            Latitude used for optional point filtering.
        lon : float | None, optional
            Longitude used for optional point filtering.
        lang : str, optional
            Preferred language code for localized fields.

        Returns
        -------
        Alert | None
            Normalized alert if the feature is valid and matches the point
            filter, otherwise ``None``.

        """
        if not isinstance(feature, dict):
            return None

        properties = feature.get('properties')
        if not isinstance(properties, dict):
            properties = {}

        event = (
            self._localized_text(properties, 'alert_name', lang)
            or self._localized_text(properties, 'alert_short_name', lang)
            or 'Weather Alert'
        )
        headline = self._localized_text(properties, 'alert_short_name', lang) or event
        identifier = (
            self.text_or_none(properties.get('id'))
            or self.text_or_none(properties.get('feature_id'))
            or self.text_or_none(feature.get('id'))
            or headline
        )

        geometry = feature.get('geometry')
        if not isinstance(geometry, dict):
            geometry = None
        if lat is not None and lon is not None:
            if geometry is None or not point_in_geometry(lat, lon, geometry):
                return None

        areas: list[str] = []
        for value in [
            self._localized_text(properties, 'feature_name', lang),
            self.text_or_none(properties.get('province')),
        ]:
            if value and value not in areas:
                areas.append(value)

        alert_url = self.text_or_none(properties.get('@id'))
        if not alert_url:
            feature_id = self.text_or_none(feature.get('id'))
            if feature_id and feature_id.startswith(('http://', 'https://')):
                alert_url = feature_id
        if not alert_url:
            links = feature.get('links')
            if isinstance(links, list):
                for link in links:
                    if not isinstance(link, dict):
                        continue
                    href = self.text_or_none(link.get('href'))
                    if not href:
                        continue
                    rel = (self.text_or_none(link.get('rel')) or '').lower()
                    if rel in {'self', 'alternate', 'about'}:
                        alert_url = href
                        break
                if not alert_url:
                    for link in links:
                        if not isinstance(link, dict):
                            continue
                        href = self.text_or_none(link.get('href'))
                        if href:
                            alert_url = href
                            break

        return Alert(
            id=identifier,
            source=source.id,
            event=event,
            headline=headline,
            url=alert_url,
            severity=self._localized_text(properties, 'risk_colour', lang) or self.text_or_none(properties.get('alert_type')),
            urgency=self._localized_text(properties, 'status', lang),
            certainty=self._localized_text(properties, 'confidence', lang),
            description=self._localized_text(properties, 'alert_text', lang)
            or self._localized_text(properties, 'description', lang),
            instruction=self._localized_text(properties, 'instruction', lang),
            onset=self.parse_datetime(properties.get('publication_datetime') or properties.get('validity_datetime')),
            expires=self.parse_datetime(properties.get('expiration_datetime') or properties.get('event_end_datetime')),
            areas=areas,
            geometry=geometry,
        )

    @staticmethod
    def _normalize_lang(value: str | None) -> str:
        """Normalize a language tag to GeoMet's supported language codes.

        Parameters
        ----------
        value : str | None
            Language tag to normalize.

        Returns
        -------
        str
            ``fr`` for French tags, otherwise ``en``.

        """
        text = (value or 'en').split(',', 1)[0].strip().lower()
        if text.startswith('fr'):
            return 'fr'
        return 'en'

    def _localized_text(self, properties: dict[str, Any], field: str, lang: str) -> str | None:
        """Return the best localized value for a GeoMet property field.

        Parameters
        ----------
        properties : dict[str, Any]
            GeoMet feature properties mapping.
        field : str
            Base field name to resolve.
        lang : str
            Preferred language code.

        Returns
        -------
        str | None
            Localized text if available, otherwise ``None``.

        """
        preferred = self.text_or_none(properties.get(f'{field}_{lang}'))
        if preferred:
            return preferred

        fallback_lang = 'en' if lang == 'fr' else 'fr'
        fallback = self.text_or_none(properties.get(f'{field}_{fallback_lang}'))
        if fallback:
            return fallback

        return self.text_or_none(properties.get(field))
