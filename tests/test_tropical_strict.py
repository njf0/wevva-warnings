"""Strict discovery distinguishes provider failure from quiet conditions."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from wevva_warnings import BackendError, TropicalSystem, get_canonical_tropical_systems, get_tropical_systems
from wevva_warnings.backends.meteofrance_reunion_tropical import _fetch_current_reunion_payloads


class StrictTropicalTests(unittest.TestCase):
    def test_strict_canonical_query_preserves_source_observations(self) -> None:
        observation = TropicalSystem(
            id='example', source='jma_tropical', name='EXAMPLE',
            classification='Tropical Storm', headline='Tropical Storm EXAMPLE',
        )
        with patch('wevva_warnings.query.get_tropical_systems', return_value=[observation]) as fetch:
            groups = get_canonical_tropical_systems(source_ids=['jma_tropical'], strict=True)
        fetch.assert_called_once_with(source_ids=['jma_tropical'], debug=False, strict=True)
        self.assertIs(groups[0].observations[0], observation)

    def test_required_listing_failures_raise_only_in_strict_mode(self) -> None:
        requests = {
            'nhc_gis_atlantic': 'wevva_warnings.backends._cap_feed.fetch_text',
            'nhc_gis_eastern_pacific': 'wevva_warnings.backends._cap_feed.fetch_text',
            'cphc_gis_central_pacific': 'wevva_warnings.backends._cap_feed.fetch_text',
            'jma_tropical': 'wevva_warnings.backends._cap_feed.fetch_text',
            'hko_tropical': 'wevva_warnings.backends._cap_feed.fetch_text',
            'bom_tropical': 'wevva_warnings.backends.bom_tropical.fetch_text',
            'cma_tropical': 'wevva_warnings.backends.cma_tropical.fetch_text',
            'pagasa_tropical': 'wevva_warnings.backends.pagasa_tropical.fetch_text',
            'meteofrance_reunion_tropical': (
                'wevva_warnings.backends.meteofrance_reunion_tropical._fetch_current_reunion_payloads'
            ),
        }
        for source, request in requests.items():
            with self.subTest(source=source), patch(request, side_effect=BackendError('offline')):
                self.assertEqual(get_canonical_tropical_systems(source_ids=[source]), [])
                with self.assertRaises(BackendError):
                    get_canonical_tropical_systems(source_ids=[source], strict=True)

    def test_successful_empty_responses_remain_empty_in_strict_mode(self) -> None:
        fixtures = (
            ('nhc_gis_atlantic', 'wevva_warnings.backends._cap_feed.fetch_text', '<rss><channel/></rss>'),
            ('jma_tropical', 'wevva_warnings.backends._cap_feed.fetch_text', '<feed/>'),
            ('hko_tropical', 'wevva_warnings.backends._cap_feed.fetch_text', '<TropicalCycloneList/>'),
            ('bom_tropical', 'wevva_warnings.backends.bom_tropical.fetch_text', ''),
            ('cma_tropical', 'wevva_warnings.backends.cma_tropical.fetch_text', '{"typhoonList": []}'),
            ('pagasa_tropical', 'wevva_warnings.backends.pagasa_tropical.fetch_text', '<p>No active tropical cyclone</p>'),
            ('meteofrance_reunion_tropical',
             'wevva_warnings.backends.meteofrance_reunion_tropical._fetch_current_reunion_payloads', []),
        )
        for source, request, payload in fixtures:
            with self.subTest(source=source), patch(request, return_value=payload):
                self.assertEqual(get_canonical_tropical_systems(source_ids=[source], strict=True), [])

    def test_failed_linked_discovery_cannot_become_a_quiet_result(self) -> None:
        cases = (
            ('bom_tropical', 'wevva_warnings.backends.bom_tropical.fetch_text', None,
             ['IDQ65248.GML', BackendError('product unavailable')]),
            ('cma_tropical', 'wevva_warnings.backends.cma_tropical.fetch_text', None,
             ['{"typhoonList": [[1234, "NAME", "start"]]}', BackendError('detail unavailable')]),
            ('hko_tropical', 'wevva_warnings.backends.hko.fetch_text',
             '<TropicalCycloneList><TropicalCyclone><TropicalCycloneID>2601</TropicalCycloneID>'
             '<TropicalCycloneURL>https://www.hko.gov.hk/track.xml</TropicalCycloneURL>'
             '</TropicalCyclone></TropicalCycloneList>', [BackendError('track unavailable')]),
        )
        for source, request, root, responses in cases:
            with self.subTest(source=source):
                root_patch = patch('wevva_warnings.backends.hko.fetch_feed_root', return_value=(
                    ElementTree.fromstring(root) if root else None
                ))
                with root_patch, patch(request, side_effect=responses):
                    with self.assertRaises(BackendError):
                        get_tropical_systems(source_ids=[source], strict=True)

        with (
            patch('wevva_warnings.backends.jma_tropical.fetch_feed_root', return_value=ElementTree.fromstring('<feed/>')),
            patch('wevva_warnings.backends.jma_tropical._jma_tropical_documents', return_value=[('https://example.test/current.xml', 'VPTW60')]),
            patch('wevva_warnings.backends.jma_tropical.fetch_text', side_effect=BackendError('report unavailable')),
        ):
            with self.assertRaises(BackendError):
                get_tropical_systems(source_ids=['jma_tropical'], strict=True)

    def test_reunion_linked_trajectory_failures_are_not_swallowed(self) -> None:
        for strict in (False, True):
            with (
                self.subTest(strict=strict),
                patch('wevva_warnings.backends.meteofrance_reunion_tropical._prime_meteofrance_session'),
                patch('wevva_warnings.backends.meteofrance_reunion_tropical._session_token', return_value='test-token'),
                patch('wevva_warnings.backends.meteofrance_reunion_tropical._fetch_meteofrance_json',
                      side_effect=[{'cyclone_list': [{'cyclone_id': '1'}]}, BackendError('trajectory unavailable')]),
            ):
                if strict:
                    with self.assertRaises(BackendError):
                        _fetch_current_reunion_payloads(season='20262027', debug=False, strict=True)
                else:
                    self.assertEqual(_fetch_current_reunion_payloads(season='20262027', debug=False), [])

    def test_invalid_listing_payloads_do_not_confirm_quiet_conditions(self) -> None:
        for source, request, payload in (
            ('jma_tropical', 'wevva_warnings.backends._cap_feed.fetch_text', 'not XML'),
            ('cma_tropical', 'wevva_warnings.backends.cma_tropical.fetch_text', 'not JSONP'),
            ('pagasa_tropical', 'wevva_warnings.backends.pagasa_tropical.fetch_text', '<h1>Maintenance</h1>'),
        ):
            with self.subTest(source=source), patch(request, return_value=payload):
                self.assertEqual(get_tropical_systems(source_ids=[source]), [])
                with self.assertRaises(BackendError):
                    get_tropical_systems(source_ids=[source], strict=True)


if __name__ == '__main__':
    unittest.main()
