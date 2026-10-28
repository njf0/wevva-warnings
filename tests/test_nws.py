"""Fixture-driven tests for NWS affected-zone geometry enrichment."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from wevva_warnings._debug import bind_progress_callback
from wevva_warnings.backends.base import BackendError
from wevva_warnings.backends.nws import NWSBackend, _fetch_zone_geometry
from wevva_warnings.registry import get_source


FIXTURE_DIR = Path(__file__).resolve().parent / 'data' / 'nws'
with (FIXTURE_DIR / 'alerts.json').open(encoding='utf-8') as handle:
    ALERTS_FIXTURE = json.load(handle)
with (FIXTURE_DIR / 'zones.json').open(encoding='utf-8') as handle:
    ZONES_FIXTURE = json.load(handle)


class NWSBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        _fetch_zone_geometry.cache_clear()
        self.backend = NWSBackend()
        self.source = get_source('nws')
        assert self.source is not None

    def _payload(self, *alert_ids: str) -> dict[str, object]:
        selected = [
            deepcopy(feature)
            for feature in ALERTS_FIXTURE['features']
            if feature['properties']['id'] in alert_ids
        ]
        return {'type': 'FeatureCollection', 'features': selected}

    def _fetcher(
        self,
        payload: dict[str, object],
        *,
        failures: set[str] | None = None,
    ) -> Mock:
        failed_urls = failures or set()

        def fetch(url: str, **_: object) -> object:
            if url == self.source.url:
                return deepcopy(payload)
            if url in failed_urls:
                raise BackendError('fixture zone failure')
            return deepcopy(ZONES_FIXTURE[url])

        return Mock(side_effect=fetch)

    def _zone_requests(self, fetch_json: Mock) -> list[str]:
        return [
            call.args[0]
            for call in fetch_json.call_args_list
            if call.args[0] != self.source.url
        ]

    def test_explicit_geometry_wins_and_raw_nws_metadata_is_preserved(self) -> None:
        payload = self._payload('explicit')
        explicit_geometry = deepcopy(payload['features'][0]['geometry'])
        fetch_json = self._fetcher(payload)

        with patch('wevva_warnings.backends.nws.fetch_json', fetch_json):
            alerts = self.backend.fetch_alerts(self.source)

        self.assertEqual(alerts[0].geometry, explicit_geometry)
        self.assertEqual(alerts[0].geocodes, {'SAME': ['036001'], 'UGC': ['NYZ001']})
        self.assertEqual(
            alerts[0].parameters,
            {
                'VTEC': ['/O.NEW.KOKX.FL.W.0001.260101T0000Z-260101T0600Z/'],
                'affectedZones': ['https://api.weather.gov/zones/forecast/NYZ001'],
            },
        )
        self.assertEqual(self._zone_requests(fetch_json), [])

    def test_single_affected_zone_supplies_polygon_geometry(self) -> None:
        payload = self._payload('single')
        fetch_json = self._fetcher(payload)

        with patch('wevva_warnings.backends.nws.fetch_json', fetch_json):
            alerts = self.backend.fetch_alerts(self.source)

        self.assertEqual(alerts[0].geometry['type'], 'Polygon')
        self.assertEqual(alerts[0].geometry['bbox'], [-75.0, 40.0, -74.0, 41.0])
        self.assertEqual(
            self._zone_requests(fetch_json),
            ['https://api.weather.gov/zones/forecast/NYZ001'],
        )

    def test_multiple_affected_zones_combine_polygon_and_multipolygon_parts(self) -> None:
        payload = self._payload('multiple')
        fetch_json = self._fetcher(payload)

        with patch('wevva_warnings.backends.nws.fetch_json', fetch_json):
            alerts = self.backend.fetch_alerts(self.source)

        self.assertEqual(alerts[0].geometry['type'], 'MultiPolygon')
        self.assertEqual(len(alerts[0].geometry['coordinates']), 3)
        self.assertEqual(alerts[0].geometry['bbox'], [-82.0, 38.0, -76.0, 43.0])
        self.assertEqual(
            self._zone_requests(fetch_json),
            [
                'https://api.weather.gov/zones/county/NYC001',
                'https://api.weather.gov/zones/fire/NYZ201',
            ],
        )

    def test_affected_zone_fetches_emit_geometry_progress(self) -> None:
        payload = self._payload('multiple')
        fetch_json = self._fetcher(payload)
        events: list[tuple[str, dict[str, object]]] = []

        with (
            patch('wevva_warnings.backends.nws.fetch_json', fetch_json),
            bind_progress_callback(
                lambda event, details: events.append((event, details))
            ),
        ):
            self.backend.fetch_alerts(self.source)

        self.assertEqual(
            events,
            [
                (
                    'alerts_total',
                    {'source': 'nws', 'total': 2, 'phase': 'geometry'},
                ),
                (
                    'alerts_checked',
                    {
                        'source': 'nws',
                        'completed': 1,
                        'total': 2,
                        'phase': 'geometry',
                    },
                ),
                (
                    'alerts_checked',
                    {
                        'source': 'nws',
                        'completed': 2,
                        'total': 2,
                        'phase': 'geometry',
                    },
                ),
            ],
        )

    def test_shared_zone_is_requested_once_and_success_is_cached(self) -> None:
        payload = self._payload('shared-one', 'shared-two')
        fetch_json = self._fetcher(payload)

        with patch('wevva_warnings.backends.nws.fetch_json', fetch_json):
            first = self.backend.fetch_alerts(self.source)
            second = self.backend.fetch_alerts(self.source)

        self.assertEqual([alert.geometry['type'] for alert in first], ['Polygon', 'Polygon'])
        self.assertEqual([alert.geometry['type'] for alert in second], ['Polygon', 'Polygon'])
        self.assertIsNot(first[0].geometry, first[1].geometry)
        self.assertEqual(
            self._zone_requests(fetch_json),
            ['https://api.weather.gov/zones/marine/ANZ001'],
        )

    def test_one_failed_zone_does_not_discard_other_resolved_boundaries(self) -> None:
        failed_url = 'https://api.weather.gov/zones/forecast/NYZ999'
        payload = self._payload('partial')
        fetch_json = self._fetcher(payload, failures={failed_url})

        with patch('wevva_warnings.backends.nws.fetch_json', fetch_json):
            alerts = self.backend.fetch_alerts(self.source)

        self.assertEqual(alerts[0].geometry['type'], 'Polygon')
        self.assertEqual(alerts[0].geometry['bbox'], [-75.0, 40.0, -74.0, 41.0])
        self.assertEqual(
            self._zone_requests(fetch_json),
            [
                'https://api.weather.gov/zones/forecast/NYZ001',
                failed_url,
            ],
        )

    def test_geometryless_alert_without_supported_zone_remains_geometryless(self) -> None:
        payload = self._payload('geometryless')
        fetch_json = self._fetcher(payload)

        with patch('wevva_warnings.backends.nws.fetch_json', fetch_json):
            alerts = self.backend.fetch_alerts(self.source)

        self.assertIsNone(alerts[0].geometry)
        self.assertEqual(alerts[0].geocodes, {'UGC': ['NYZ404']})
        self.assertEqual(
            alerts[0].parameters['affectedZones'],
            [
                'https://api.weather.gov/zones/public/NYZ404',
                'https://example.com/zones/forecast/NYZ404',
            ],
        )
        self.assertEqual(self._zone_requests(fetch_json), [])


if __name__ == '__main__':
    unittest.main()
