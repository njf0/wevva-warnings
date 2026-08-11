"""Tests for low-volume national CAP feeds handled by ``generic_cap``."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
import warnings
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


SOURCE_CASES = (
    {
        'id': 'imn_costa_rica',
        'country': 'CR',
        'lang': 'es',
        'lat': 10.0,
        'lon': -84.0,
        'event': 'Vientos fuertes',
        'area': 'Costa Rica',
        'feed_url': 'https://cap-sources.s3.amazonaws.com/cr-imn-es/rss.xml',
        'alert_url': 'https://cap-sources.s3.amazonaws.com/cr-imn-es/fixture-alert.xml',
    },
    {
        'id': 'ema_egypt',
        'country': 'EG',
        'lang': 'en',
        'lat': 30.0,
        'lon': 31.0,
        'event': 'Heat wave',
        'area': 'Greater Cairo',
        'feed_url': 'https://cap-sources.s3.amazonaws.com/eg-ema-en/rss.xml',
        'alert_url': 'https://cap-sources.s3.amazonaws.com/eg-ema-en/fixture-alert.xml',
    },
    {
        'id': 'irimo_en',
        'country': 'IR',
        'lang': 'en',
        'lat': 30.0,
        'lon': 50.0,
        'event': 'High seas',
        'area': 'Persian Gulf',
        'feed_url': 'https://cap-sources.s3.amazonaws.com/ir-irimo-en/rss.xml',
        'alert_url': 'https://cap-sources.s3.amazonaws.com/ir-irimo-en/fixture-alert.xml',
    },
    {
        'id': 'kuwait_met',
        'country': 'KW',
        'lang': 'en',
        'lat': 29.3,
        'lon': 47.5,
        'event': 'Fog',
        'area': 'State of Kuwait',
        'feed_url': 'https://www.met.gov.kw/rss_eng/kuwait_cap.xml',
        'alert_url': 'https://www.met.gov.kw/XML/cap-fixture.xml',
    },
    {
        'id': 'pmd_pakistan',
        'country': 'PK',
        'lang': 'en',
        'lat': 33.0,
        'lon': 73.0,
        'event': 'Heavy rain',
        'area': 'Punjab',
        'feed_url': 'https://cap-sources.s3.amazonaws.com/pk-pmd-en/rss.xml',
        'alert_url': 'https://cap-sources.s3.amazonaws.com/pk-pmd-en/fixture-alert.xml',
    },
)


def _rss_feed(case: dict[str, object]) -> str:
    """Build a representative RSS feed containing one linked CAP document."""
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{case['id']} warnings</title>
    <item>
      <title>{case['event']}</title>
      <link>{case['alert_url']}</link>
      <guid>fixture-{case['id']}</guid>
    </item>
  </channel>
</rss>
"""


def _cap_document(case: dict[str, object]) -> str:
    """Build a polygonal CAP document around the case's matching point."""
    lat = float(case['lat'])
    lon = float(case['lon'])
    polygon = (
        f'{lat - 0.5},{lon - 0.5} {lat - 0.5},{lon + 0.5} '
        f'{lat + 0.5},{lon + 0.5} {lat + 0.5},{lon - 0.5} '
        f'{lat - 0.5},{lon - 0.5}'
    )
    return f"""\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>fixture-{case['id']}</identifier>
  <sender>fixtures@wevva.example</sender>
  <sent>2026-08-11T09:00:00Z</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>{case['lang']}</language>
    <category>Met</category>
    <event>{case['event']}</event>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <onset>2026-08-11T10:00:00Z</onset>
    <expires>2026-08-11T18:00:00Z</expires>
    <headline>{case['event']} alert</headline>
    <area>
      <areaDesc>{case['area']}</areaDesc>
      <polygon>{polygon}</polygon>
    </area>
  </info>
</alert>
"""


class LowVolumeGenericCAPSourceTests(unittest.TestCase):
    def test_sources_are_registered_and_selected_for_declared_languages(self) -> None:
        for case in SOURCE_CASES:
            with self.subTest(source=case['id']):
                source = get_source(str(case['id']))

                self.assertIsNotNone(source)
                assert source is not None
                self.assertEqual(source.country_code, case['country'])
                self.assertEqual(source.backend, 'generic_cap')
                self.assertEqual(source.url, case['feed_url'])
                self.assertEqual(source.lang, case['lang'])
                self.assertEqual(get_alert_sources_for_country(str(case['country'])), [source])
                self.assertEqual(
                    get_alert_sources_for_country(str(case['country']), lang=str(case['lang'])),
                    [source],
                )

    def test_linked_cap_alerts_match_points_for_each_source(self) -> None:
        for case in SOURCE_CASES:
            with self.subTest(source=case['id']):
                source = get_source(str(case['id']))
                assert source is not None
                responses = {
                    source.url: _rss_feed(case),
                    str(case['alert_url']): _cap_document(case),
                }

                with patch(
                    'wevva_warnings.backends.generic_cap.fetch_text',
                    side_effect=lambda url, **_: responses[url],
                ) as fetch_text:
                    alerts = get_alerts_for_point(
                        float(case['lat']),
                        float(case['lon']),
                        str(case['country']),
                        lang=str(case['lang']),
                    )

                self.assertEqual([alert.id for alert in alerts], [f"fixture-{case['id']}"])
                self.assertEqual(alerts[0].source, case['id'])
                self.assertEqual(alerts[0].event, case['event'])
                self.assertEqual(alerts[0].area_names, [case['area']])
                self.assertEqual(alerts[0].geometry['type'], 'Polygon')
                self.assertEqual([call.args[0] for call in fetch_text.call_args_list], [source.url, case['alert_url']])

    def test_costa_rica_uses_standard_unsupported_language_fallback(self) -> None:
        source = get_source('imn_costa_rica')
        assert source is not None

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            sources = get_alert_sources_for_country('CR', lang='en')

        self.assertEqual(sources, [source])
        self.assertEqual(len(caught), 1)

    def test_egypt_alert_honours_active_only_and_standard_progress(self) -> None:
        case = next(case for case in SOURCE_CASES if case['id'] == 'ema_egypt')
        source = get_source('ema_egypt')
        assert source is not None
        responses = {
            source.url: _rss_feed(case),
            str(case['alert_url']): _cap_document(case),
        }
        events: list[tuple[str, dict[str, object]]] = []

        with (
            patch(
                'wevva_warnings.backends.generic_cap.fetch_text',
                side_effect=lambda url, **_: responses[url],
            ),
            patch('wevva_warnings.query._utc_now', return_value=datetime(2026, 8, 11, 12, 0, tzinfo=UTC)),
        ):
            alerts = get_alerts_for_point(
                float(case['lat']),
                float(case['lon']),
                'EG',
                active_only=True,
                progress=lambda event, payload: events.append((event, payload)),
            )

        self.assertEqual([alert.id for alert in alerts], ['fixture-ema_egypt'])
        self.assertEqual(
            [event for event, _ in events],
            [
                'query_started',
                'sources_total',
                'source_started',
                'alerts_total',
                'alerts_checked',
                'alerts_total',
                'alerts_checked',
                'source_finished',
                'finished',
            ],
        )
        self.assertEqual(events[-1][1], {'alert_count': 1})

        with (
            patch(
                'wevva_warnings.backends.generic_cap.fetch_text',
                side_effect=lambda url, **_: responses[url],
            ),
            patch('wevva_warnings.query._utc_now', return_value=datetime(2026, 8, 11, 19, 0, tzinfo=UTC)),
        ):
            expired = get_alerts_for_point(float(case['lat']), float(case['lon']), 'EG', active_only=True)

        self.assertEqual(expired, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
