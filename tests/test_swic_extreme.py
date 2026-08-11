"""Tests for the global WMO SWIC Extreme-warning discovery helper."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_swic_extreme_alerts
from wevva_warnings.backends.base import BackendError
from wevva_warnings.backends.swic_extreme import SWICExtremeBackend
from wevva_warnings.registry import get_source


SWIC_EXTREME_FEATURES = {
    'features': [
        {
            'properties': {
                'capurl': 'example-nmhs-en/2026/08/09/08/00/00-storm.xml',
                'event': 'Severe thunderstorm',
                'headline': '',
                'description': 'Damaging wind and large hail.',
                's': 4,
                'u': 1,
                'c': 2,
                'onset': '2026-08-09T10:00:00Z',
                'expires': '2026-08-09T16:00:00Z',
                'areadesc': 'North District',
                'marine': '0',
                'file_name': 'example.geojson',
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[10.0, 50.0], [10.1, 50.0], [10.1, 50.1], [10.0, 50.0]]],
            },
        },
        {
            'properties': {
                'capurl': 'example-nmhs-en/2026/08/09/08/00/00-storm.xml',
                'event': 'Severe thunderstorm',
                'headline': '',
                'description': 'Damaging wind and large hail.',
                's': 4,
                'u': 1,
                'c': 2,
                'onset': '2026-08-09T10:00:00Z',
                'expires': '2026-08-09T16:00:00Z',
                'areadesc': 'South District',
                'marine': '0',
                'file_name': 'example.geojson',
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[10.2, 50.0], [10.3, 50.0], [10.3, 50.1], [10.2, 50.0]]],
            },
        },
        {
            'properties': {
                'capurl': 'example-nmhs-en/2026/08/09/07/00/00-marine.xml',
                'event': 'Hurricane-force wind',
                'headline': 'Hurricane-force marine warning',
                'description': 'No description',
                's': 4,
                'onset': '2026-08-09T10:00:00Z',
                'expires': '2026-08-09T16:00:00Z',
                'areadesc': 'Open sea',
                'marine': '1',
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[12.0, 50.0], [12.1, 50.0], [12.1, 50.1], [12.0, 50.0]]],
            },
        },
        {
            'properties': {
                'capurl': 'example-nmhs-en/2026/08/09/04/00/00-expired.xml',
                'event': 'Extreme heat',
                'headline': 'Expired heat warning',
                's': 4,
                'onset': '2026-08-09T01:00:00Z',
                'expires': '2026-08-09T11:00:00Z',
                'areadesc': 'Inland',
                'marine': '0',
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[14.0, 50.0], [14.1, 50.0], [14.1, 50.1], [14.0, 50.0]]],
            },
        },
        {
            'properties': {
                'capurl': 'example-nmhs-en/2026/08/09/09/00/00-invalid.xml',
                'event': 'Severe thunderstorm',
                's': 4,
                'marine': '0',
            },
            'geometry': {'type': 'Point', 'coordinates': [10.0, 50.0]},
        },
    ]
}


class SWICExtremeTests(unittest.TestCase):
    def test_global_source_is_visible_but_not_country_routed(self) -> None:
        source = get_source('swic_extreme')

        self.assertIsNotNone(source)
        assert source is not None
        self.assertIsNone(source.country_code)
        self.assertNotIn(source, get_alert_sources_for_country('FI'))

    def test_backend_groups_polygon_rows_and_excludes_marine_by_default(self) -> None:
        source = get_source('swic_extreme')
        assert source is not None

        with patch('wevva_warnings.backends.swic_extreme.fetch_json', return_value=SWIC_EXTREME_FEATURES) as fetch_json:
            alerts = SWICExtremeBackend().fetch_alerts(source)

        self.assertEqual(
            [alert.id for alert in alerts],
            [
                'example-nmhs-en/2026/08/09/04/00/00-expired.xml',
                'example-nmhs-en/2026/08/09/08/00/00-storm.xml',
            ],
        )
        storm = alerts[1]
        self.assertEqual(storm.source, 'swic_extreme')
        self.assertEqual(storm.headline, 'Severe thunderstorm — North District, South District')
        self.assertEqual(storm.severity, 'Extreme')
        self.assertEqual(storm.area_names, ['North District', 'South District'])
        self.assertEqual(storm.geometry['type'], 'MultiPolygon')
        self.assertEqual(storm.geometry['bbox'], [10.0, 50.0, 10.3, 50.1])
        self.assertEqual(storm.parameters['WMO SWIC Severity Code'], ['4'])
        self.assertEqual(storm.parameters['WMO SWIC Urgency Code'], ['1'])
        self.assertEqual(storm.parameters['WMO SWIC Certainty Code'], ['2'])
        self.assertEqual(storm.parameters['WMO SWIC geometry file'], ['example.geojson'])
        self.assertEqual(
            storm.url,
            'https://severeweather.wmo.int/v2/cap-alerts/example-nmhs-en/2026/08/09/08/00/00-storm.xml',
        )
        self.assertEqual(fetch_json.call_args.kwargs['params']['cql_filter'], "s = 4 AND marine = '0'")
        self.assertEqual(fetch_json.call_args.kwargs['timeout'], 30.0)

    def test_public_helper_filters_activity_locally_and_attaches_source_info(self) -> None:
        now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
        with (
            patch('wevva_warnings.backends.swic_extreme.fetch_json', return_value=SWIC_EXTREME_FEATURES),
            patch('wevva_warnings.query._utc_now', return_value=now),
        ):
            alerts = get_swic_extreme_alerts()

        self.assertEqual([alert.id for alert in alerts], ['example-nmhs-en/2026/08/09/08/00/00-storm.xml'])
        self.assertIsNotNone(alerts[0].source_info)
        assert alerts[0].source_info is not None
        self.assertEqual(alerts[0].source_info.id, 'swic_extreme')

    def test_public_helper_can_include_marine_and_inactive_candidates(self) -> None:
        with patch('wevva_warnings.backends.swic_extreme.fetch_json', return_value=SWIC_EXTREME_FEATURES) as fetch_json:
            alerts = get_swic_extreme_alerts(active_only=False, include_marine=True)

        self.assertEqual(
            [alert.id for alert in alerts],
            [
                'example-nmhs-en/2026/08/09/04/00/00-expired.xml',
                'example-nmhs-en/2026/08/09/07/00/00-marine.xml',
                'example-nmhs-en/2026/08/09/08/00/00-storm.xml',
            ],
        )
        self.assertIsNone(alerts[1].description)
        self.assertEqual(fetch_json.call_args.kwargs['params']['cql_filter'], 's = 4')

    def test_wfs_failure_is_non_fatal(self) -> None:
        with patch('wevva_warnings.backends.swic_extreme.fetch_json', side_effect=BackendError('unavailable')):
            alerts = get_swic_extreme_alerts()

        self.assertEqual(alerts, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
