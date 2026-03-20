"""Tests for the GeoMet backend."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings.backends.geomet import GeoMetBackend
from wevva_warnings.registry import get_source

MATCHING_FEATURE = {
    'id': 'match',
    'geometry': {
        'type': 'Polygon',
        'coordinates': [[[-101.0, 50.0], [-100.0, 50.0], [-100.0, 51.0], [-101.0, 51.0], [-101.0, 50.0]]],
    },
    'properties': {
        'id': 'match',
        'alert_name_en': 'Snowfall Warning',
        'alert_name_fr': 'Alerte de neige',
        'alert_short_name_en': 'Snowfall Warning',
        'alert_short_name_fr': 'Alerte de neige',
        'risk_colour_en': 'Red',
        'alert_text_en': 'Heavy snow expected.',
        'alert_text_fr': 'De fortes chutes de neige sont prevues.',
        'publication_datetime': '2026-03-12T10:00:00Z',
        'expiration_datetime': '2026-03-12T18:00:00Z',
        'feature_name_en': 'Match Area',
        'feature_name_fr': 'Zone correspondante',
        'status_en': 'Issued',
        'status_fr': 'Emis',
        'province': 'MB',
    },
    'links': [{'href': 'https://api.weather.gc.ca/collections/weather-alerts/items/match', 'rel': 'self'}],
}

NON_MATCHING_FEATURE = {
    'id': 'miss',
    'geometry': {
        'type': 'Polygon',
        'coordinates': [[[-80.0, 43.0], [-79.0, 43.0], [-79.0, 44.0], [-80.0, 44.0], [-80.0, 43.0]]],
    },
    'properties': {
        'id': 'miss',
        'alert_name_en': 'Wind Warning',
        'alert_short_name_en': 'Wind Warning',
        'risk_colour_en': 'Yellow',
        'alert_text_en': 'Strong winds expected.',
        'publication_datetime': '2026-03-12T10:00:00Z',
        'expiration_datetime': '2026-03-12T18:00:00Z',
        'feature_name_en': 'Miss Area',
        'province': 'ON',
    },
}


class GeoMetBackendTests(unittest.TestCase):
    def test_fetch_alerts_prefers_requested_language_and_keeps_point_match(self) -> None:
        backend = GeoMetBackend()
        source = get_source('geomet')
        assert source is not None

        payload = {'features': [MATCHING_FEATURE, NON_MATCHING_FEATURE]}
        with patch('wevva_warnings.backends.geomet.fetch_json', return_value=payload) as fetch_json:
            alerts = backend.fetch_alerts(source, lat=50.5, lon=-100.5, lang='fr-CA')

        self.assertEqual(fetch_json.call_args.kwargs['params']['lang'], 'fr')
        self.assertEqual([alert.id for alert in alerts], ['match'])
        self.assertEqual(alerts[0].headline, 'Alerte de neige')
        self.assertEqual(alerts[0].url, 'https://api.weather.gc.ca/collections/weather-alerts/items/match')
