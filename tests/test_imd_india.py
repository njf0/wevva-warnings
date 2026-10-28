"""Focused tests for the combined WMO/SACHET IMD backend."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wevva_warnings import match_alerts_to_point
from wevva_warnings.backends.base import BackendError
from wevva_warnings.backends.imd_india import IMDIndiaBackend, SACHET_RSS_URL
from wevva_warnings.registry import get_source


FIXTURES = Path(__file__).parent / 'data' / 'imd_india'
RICH_ALERT = (FIXTURES / 'rich_alert.xml').read_text(encoding='utf-8')
RELAY_ALERT = (FIXTURES / 'relay_alert.xml').read_text(encoding='utf-8')
RELAY_POLYGON = (FIXTURES / 'relay_polygon.xml').read_text(encoding='utf-8')
WMO_DUPLICATE = (FIXTURES / 'wmo_duplicate.xml').read_text(encoding='utf-8')
NOWCASTS = json.loads((FIXTURES / 'nowcasts.json').read_text(encoding='utf-8'))

RICH_URL = 'https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1792063527554028'
RELAY_URL = 'https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1792067024541019'
POLYGON_URL = 'https://sachet.ndma.gov.in/cap_public_website/FetchPolygonXMLFile?identifier=1792067024541019'
CWC_URL = 'https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1792067000000001'
MALFORMED_URL = 'https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1792067000000002'
WMO_URL = 'https://cap-sources.s3.amazonaws.com/in-imd-en/imd-duplicate.xml'

EMPTY_WMO_FEED = """\
<rss version="2.0"><channel>
  <pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate>
</channel></rss>
"""


def _wmo_feed(*urls: str) -> str:
    items = ''.join(f'<item><link>{url}</link></item>' for url in urls)
    return (
        '<rss version="2.0"><channel>'
        '<pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate>'
        f'{items}</channel></rss>'
    )


def _sachet_feed(*items: tuple[str, str]) -> str:
    body = ''.join(
        '<item>'
        f'<link>{url}</link>'
        f'<author>controlroom@ndma.gov.in ({author})</author>'
        '</item>'
        for url, author in items
    )
    return (
        '<rss version="2.0"><channel>'
        '<pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate>'
        f'{body}</channel></rss>'
    )


class IMDIndiaBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = get_source('imd_india')
        assert self.source is not None
        self.backend = IMDIndiaBackend()

    def _fetch(
        self,
        *,
        wmo_feed: str = EMPTY_WMO_FEED,
        sachet_feed: str,
        wmo_documents: dict[str, str] | None = None,
        sachet_documents: dict[str, str | Exception],
        nowcasts: object = None,
        debug: bool = False,
    ):
        wmo_documents = wmo_documents or {}
        if nowcasts is None:
            nowcasts = {'type': 'FeatureCollection', 'features': []}

        def direct_fetch(url: str, **_: object) -> str:
            if url == SACHET_RSS_URL:
                return sachet_feed
            return wmo_documents[url]

        def sachet_fetch(url: str, **_: object) -> str:
            result = sachet_documents[url]
            if isinstance(result, Exception):
                raise result
            return result

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', return_value=wmo_feed),
            patch('wevva_warnings.backends.imd_india.fetch_text', side_effect=direct_fetch),
            patch('wevva_warnings.backends.imd_india.fetch_json', return_value=nowcasts),
            patch.object(self.backend._sachet_session, 'fetch_text', side_effect=sachet_fetch) as cached_fetch,
        ):
            alerts = self.backend.fetch_alerts(self.source, debug=debug)
        return alerts, cached_fetch

    def test_empty_wmo_feed_uses_rich_english_sachet_alert_and_excludes_cwc(self) -> None:
        feed = _sachet_feed(
            (RICH_URL, 'IMD Jaipur'),
            (CWC_URL, 'CWC'),
            (MALFORMED_URL, 'IMD Patna'),
        )
        alerts, cached_fetch = self._fetch(
            sachet_feed=feed,
            sachet_documents={RICH_URL: RICH_ALERT, MALFORMED_URL: '<not-cap'},
        )

        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.id, 'IN-1792063527554028_57')
        self.assertEqual(alert.event, 'Moderate Thunderstorms with surface wind')
        self.assertEqual(alert.headline, 'Moderate thunderstorms with surface wind are likely over Ajmer.')
        self.assertEqual(alert.description, 'Light to moderate rain with gusty surface wind is likely at isolated places.')
        self.assertEqual(alert.instruction, 'Take safe shelter and avoid trees.')
        self.assertEqual((alert.severity, alert.urgency, alert.certainty), ('Moderate', 'Expected', 'Possible'))
        self.assertEqual(alert.onset.isoformat(), '2026-10-15T16:58:10+05:30')
        self.assertEqual(alert.expires.isoformat(), '2026-10-15T19:54:00+05:30')
        self.assertTrue(alert.is_active(datetime(2026, 10, 15, 12, 0, tzinfo=UTC)))
        self.assertEqual(alert.area_names, ['Ajmer district of Rajasthan'])
        self.assertEqual(alert.geocodes, {'LGD District Code': ['86']})
        self.assertEqual(alert.geometry['type'], 'Polygon')
        self.assertEqual(alert.parameters['SACHET CAP sent'], ['2026-10-15T16:55:03+05:30'])
        self.assertEqual(alert.parameters['wevva:ingestion route'], ['NDMA SACHET relay'])
        self.assertEqual(
            match_alerts_to_point([alert], lat=26.5, lon=74.7, active_only=False),
            [alert],
        )
        self.assertEqual(match_alerts_to_point([alert], lat=28.6, lon=77.2, active_only=False), [])
        requested = [call.args[0] for call in cached_fetch.call_args_list]
        self.assertEqual(requested, [RICH_URL, MALFORMED_URL])
        self.assertNotIn(CWC_URL, requested)
        self.assertNotIn('FetchPolygonXMLFile', ' '.join(requested))

    def test_state_relay_requires_imd_reference_and_uses_external_polygon(self) -> None:
        alerts, cached_fetch = self._fetch(
            sachet_feed=_sachet_feed((RELAY_URL, 'IMD Bengaluru')),
            sachet_documents={RELAY_URL: RELAY_ALERT, POLYGON_URL: RELAY_POLYGON},
        )

        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.parameters['SACHET CAP sender'], ['Karnataka-SNDMC'])
        self.assertEqual(
            alert.parameters['SACHET CAP references'],
            ['IMD-Bengaluru,IN-1792067024541019_51,2026-10-15T17:53:17+05:30'],
        )
        self.assertEqual(alert.geocodes['LGD District Code'], ['549', '550'])
        self.assertEqual(alert.geometry['type'], 'Polygon')
        self.assertEqual(len(alert.geometry['coordinates']), 1)
        self.assertEqual([call.args[0] for call in cached_fetch.call_args_list], [RELAY_URL, POLYGON_URL])
        self.assertEqual(match_alerts_to_point([alert], lat=13.5, lon=74.8, active_only=False), [alert])
        self.assertEqual(match_alerts_to_point([alert], lat=16.0, lon=74.8, active_only=False), [])

    def test_rss_imd_attribution_does_not_override_non_imd_cap_provenance(self) -> None:
        non_imd_relay = RELAY_ALERT.replace('IMD-Bengaluru,', 'CWC-Delhi,')
        alerts, cached_fetch = self._fetch(
            sachet_feed=_sachet_feed((RELAY_URL, 'IMD Bengaluru')),
            sachet_documents={RELAY_URL: non_imd_relay},
        )

        self.assertEqual(alerts, [])
        self.assertEqual([call.args[0] for call in cached_fetch.call_args_list], [RELAY_URL])

    def test_wmo_original_and_newer_sachet_update_are_deduplicated_by_reference(self) -> None:
        alerts, _ = self._fetch(
            wmo_feed=_wmo_feed(WMO_URL),
            sachet_feed=_sachet_feed((RELAY_URL, 'IMD Bengaluru')),
            wmo_documents={WMO_URL: WMO_DUPLICATE},
            sachet_documents={RELAY_URL: RELAY_ALERT, POLYGON_URL: RELAY_POLYGON},
        )

        self.assertEqual([alert.id for alert in alerts], ['IN-1792067024541019_19'])
        self.assertEqual(alerts[0].parameters['wevva:ingestion route'], ['NDMA SACHET relay'])

    def test_equivalent_sachet_documents_collapse_after_english_selection(self) -> None:
        copy_number = '1792063527554099'
        copy_url = RICH_URL.replace('1792063527554028', copy_number)
        copy_alert = RICH_ALERT.replace('IN-1792063527554028_57', f'IN-{copy_number}_57')
        alerts, _ = self._fetch(
            sachet_feed=_sachet_feed(
                (RICH_URL, 'IMD Jaipur'),
                (copy_url, 'IMD Jaipur'),
            ),
            sachet_documents={RICH_URL: RICH_ALERT, copy_url: copy_alert},
        )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].headline, 'Moderate thunderstorms with surface wind are likely over Ajmer.')

    def test_cancel_references_remove_the_live_alert(self) -> None:
        cancel_url = 'https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1792067024541020'
        cancel = RELAY_ALERT.replace(
            '<cap:identifier>IN-1792067024541019_19</cap:identifier>',
            '<cap:identifier>IN-1792067024541020_19</cap:identifier>',
        ).replace('<cap:msgType>Update</cap:msgType>', '<cap:msgType>Cancel</cap:msgType>')
        alerts, _ = self._fetch(
            sachet_feed=_sachet_feed((RELAY_URL, 'IMD Bengaluru'), (cancel_url, 'IMD Bengaluru')),
            sachet_documents={RELAY_URL: RELAY_ALERT, POLYGON_URL: RELAY_POLYGON, cancel_url: cancel},
        )

        self.assertEqual(alerts, [])

    def test_one_sachet_document_failure_does_not_destroy_other_alerts(self) -> None:
        failed_url = 'https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1792067000000003'
        alerts, _ = self._fetch(
            sachet_feed=_sachet_feed((failed_url, 'IMD Patna'), (RICH_URL, 'IMD Jaipur')),
            sachet_documents={failed_url: BackendError('temporary failure'), RICH_URL: RICH_ALERT},
        )

        self.assertEqual([alert.id for alert in alerts], ['IN-1792063527554028_57'])

    def test_polygon_403_disables_further_companion_requests_for_refresh(self) -> None:
        second_number = '1792067024541099'
        second_url = RELAY_URL.replace('1792067024541019', second_number)
        second_alert = RELAY_ALERT.replace('1792067024541019', second_number)
        alerts, cached_fetch = self._fetch(
            sachet_feed=_sachet_feed(
                (RELAY_URL, 'IMD Bengaluru'),
                (second_url, 'IMD Bengaluru'),
            ),
            sachet_documents={
                RELAY_URL: RELAY_ALERT,
                POLYGON_URL: BackendError('HTTP Error 403: Forbidden'),
                second_url: second_alert,
            },
        )

        self.assertTrue(alerts)
        self.assertEqual(
            [call.args[0] for call in cached_fetch.call_args_list],
            [RELAY_URL, POLYGON_URL, second_url],
        )

    def test_wfs_nowcasts_preserve_publisher_text_and_supply_geometry(self) -> None:
        alerts, _ = self._fetch(
            sachet_feed=_sachet_feed(),
            sachet_documents={},
            nowcasts=NOWCASTS,
        )

        self.assertEqual(len(alerts), 2)
        publisher_alert = alerts[0]
        self.assertEqual(
            publisher_alert.event,
            'Light thunderstorms with surface wind below 40 km/h; Moderate rain',
        )
        self.assertEqual(
            publisher_alert.headline,
            'Thunderstorms and moderate rain are likely in Kanyakumari district.',
        )
        self.assertEqual(
            publisher_alert.description,
            'Temporary disruption to outdoor activity is possible.',
        )
        self.assertEqual(publisher_alert.instruction, 'Move indoors and avoid exposed places.')
        self.assertEqual(publisher_alert.severity, 'Severe')
        self.assertIsNone(publisher_alert.urgency)
        self.assertIsNone(publisher_alert.certainty)
        self.assertEqual(publisher_alert.onset.isoformat(), '2026-10-15T19:00:00+05:30')
        self.assertEqual(publisher_alert.expires.isoformat(), '2026-10-15T22:00:00+05:30')
        self.assertEqual(publisher_alert.area_names, ['KANYAKUMARI', 'TAMILNADU'])
        self.assertEqual(publisher_alert.geocodes, {'IMD Obj_id': ['30']})
        self.assertEqual(publisher_alert.geometry['type'], 'MultiPolygon')
        self.assertEqual(
            match_alerts_to_point([publisher_alert], lat=8.5, lon=77.5, active_only=False),
            [publisher_alert],
        )
        self.assertEqual(
            match_alerts_to_point([publisher_alert], lat=12.0, lon=80.0, active_only=False),
            [],
        )

        normalized_alert = alerts[1]
        self.assertIn('Localized waterlogging', normalized_alert.event)
        self.assertEqual(
            normalized_alert.headline,
            f'{normalized_alert.event} for THIRUVANANTHAPURAM',
        )
        self.assertIsNone(normalized_alert.description)
        self.assertIsNone(normalized_alert.instruction)
        self.assertIn('wevva:normalization', normalized_alert.parameters)
        self.assertEqual(normalized_alert.expires.isoformat(), '2026-10-16T01:00:00+05:30')

    def test_debug_audit_reports_route_and_content_coverage(self) -> None:
        with self.assertLogs(level='INFO') as logs:
            self._fetch(
                sachet_feed=_sachet_feed((RICH_URL, 'IMD Jaipur')),
                sachet_documents={RICH_URL: RICH_ALERT},
                nowcasts=NOWCASTS,
                debug=True,
            )

        audit = next(message for message in logs.output if 'Provider \'imd_india\' audit:' in message)
        self.assertIn('WMO items=0', audit)
        self.assertIn('SACHET total=1', audit)
        self.assertIn('SACHET IMD-eligible=1', audit)
        self.assertIn('WFS nowcasts=2', audit)
        self.assertIn('geometry=3', audit)
        self.assertIn('description=2', audit)
        self.assertIn('instruction=2', audit)

    def test_expired_document_left_in_rss_is_not_returned(self) -> None:
        expired = RICH_ALERT.replace(
            '2026-10-15T19:54:00+05:30',
            '2026-10-15T16:00:00+05:30',
        )
        alerts, _ = self._fetch(
            sachet_feed=_sachet_feed((RICH_URL, 'IMD Jaipur')),
            sachet_documents={RICH_URL: expired},
        )

        self.assertEqual(alerts, [])

    def test_sachet_feed_failure_still_returns_wmo_alert(self) -> None:
        def direct_fetch(url: str, **_: object) -> str:
            if url == SACHET_RSS_URL:
                raise BackendError('SACHET unavailable')
            return WMO_DUPLICATE

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', return_value=_wmo_feed(WMO_URL)),
            patch('wevva_warnings.backends.imd_india.fetch_text', side_effect=direct_fetch),
            patch(
                'wevva_warnings.backends.imd_india.fetch_json',
                side_effect=BackendError('WFS unavailable'),
            ),
        ):
            alerts = self.backend.fetch_alerts(self.source)

        self.assertEqual([alert.id for alert in alerts], ['IN-1792067024541019_51'])
        self.assertEqual(alerts[0].parameters['wevva:ingestion route'], ['WMO Alert Hub mirror'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
