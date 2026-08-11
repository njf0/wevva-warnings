"""Tests for the Meteorological Service Singapore CAP source."""

from __future__ import annotations

import unittest
import warnings
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


# Captured from the official MSS CAP RSS feed on 18 February 2026. The linked
# CAP document is represented with a compact polygon so the fixture remains
# readable while exercising the provider's real RSS/CAP document pattern.
MSS_FEED = """\
<?xml version="1.0" encoding="UTF-8" ?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
  <channel>
    <atom:link rel="self" href="https://www.weather.gov.sg/files/rss/rsscapalert/rsscapalert.xml"/>
    <title>Meteorological Service Singapore</title>
    <link>https://www.weather.gov.sg/files/rss/rsscapalert/rsscapalert.xml</link>
    <description>Alerts posted by Meteorological Service Singapore</description>
    <language>en-us</language>
    <copyright>public domain</copyright>
    <item>
      <title>HEAVY RAIN WARNING</title>
      <link>https://www.weather.gov.sg/files/rss/rsscapalert/cap_20260218_171400.xml</link>
      <description>Moderate to heavy thundery showers are expected over southern, western and central areas of Singapore.</description>
      <author>MSS_CFO_Fcsters@nea.gov.sg</author>
      <category>Met</category>
      <guid>urn:oid:2.49.0.1.702.0.2026.2.18.17.14.0</guid>
    </item>
  </channel>
</rss>
"""

MSS_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>urn:oid:2.49.0.1.702.0.2026.2.18.17.14.0</identifier>
  <sender>MSS_CFO_Fcsters@nea.gov.sg</sender>
  <sent>2026-02-18T17:14:00+08:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Met</category>
    <event>Heavy Rain</event>
    <urgency>Immediate</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <onset>2026-02-18T17:20:00+08:00</onset>
    <expires>2026-02-18T18:00:00+08:00</expires>
    <senderName>METEOROLOGICAL SERVICE SINGAPORE</senderName>
    <headline>HEAVY RAIN WARNING</headline>
    <description>Moderate to heavy thundery showers are expected over southern, western and central areas of Singapore.</description>
    <web>https://www.weather.gov.sg/files/rss/rsscapalert/cap_20260218_171400.xml</web>
    <area>
      <areaDesc>southern, western and central areas of Singapore</areaDesc>
      <polygon>1.25,103.60 1.25,104.10 1.50,104.10 1.50,103.60 1.25,103.60</polygon>
    </area>
  </info>
</alert>
"""

MSS_ALERT_URL = 'https://www.weather.gov.sg/files/rss/rsscapalert/cap_20260218_171400.xml'


class SingaporeSourceTests(unittest.TestCase):
    def test_mss_source_is_selected_for_singapore_and_english_fallback(self) -> None:
        source = get_source('mss_singapore')

        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual(source.country_code, 'SG')
        self.assertEqual(source.backend, 'generic_cap')
        self.assertEqual(get_alert_sources_for_country('sg', lang='en'), [source])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fallback_sources = get_alert_sources_for_country('SG', lang='ms')

        self.assertEqual(fallback_sources, [source])
        self.assertEqual(len(caught), 1)

    def test_mss_rss_alert_matches_point_and_emits_standard_progress(self) -> None:
        source = get_source('mss_singapore')
        assert source is not None
        events: list[tuple[str, dict[str, object]]] = []

        def fake_fetch_text(url: str, **_: object) -> str:
            return {source.url: MSS_FEED, MSS_ALERT_URL: MSS_CAP}[url]

        with patch('wevva_warnings.backends.generic_cap.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = get_alerts_for_point(
                1.35,
                103.82,
                'SG',
                lang='en',
                progress=lambda event, payload: events.append((event, payload)),
            )

        self.assertEqual([alert.id for alert in alerts], ['urn:oid:2.49.0.1.702.0.2026.2.18.17.14.0'])
        self.assertEqual(alerts[0].source, source.id)
        self.assertEqual(alerts[0].url, MSS_ALERT_URL)
        self.assertEqual(alerts[0].area_names, ['southern', 'western and central areas of Singapore'])
        self.assertEqual(alerts[0].geometry['type'], 'Polygon')
        self.assertEqual([call.args[0] for call in fetch_text.call_args_list], [source.url, MSS_ALERT_URL])
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
        self.assertEqual(events[1][1], {'total': 1})
        self.assertEqual(events[-1][1], {'alert_count': 1})

    def test_mss_alert_respects_active_only(self) -> None:
        source = get_source('mss_singapore')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            return {source.url: MSS_FEED, MSS_ALERT_URL: MSS_CAP}[url]

        with patch('wevva_warnings.backends.generic_cap.fetch_text', side_effect=fake_fetch_text):
            alerts = get_alerts_for_point(1.35, 103.82, 'SG', active_only=True)

        self.assertEqual(alerts, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
