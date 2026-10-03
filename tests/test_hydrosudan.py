"""Tests for Sudan's General Administration of Nile Waters Affairs source."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


HYDROSUDAN_FEED = """\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>أحدث التنبيهات من الادارة العامة لشئون مياه النيل</title>
    <link>https://hydrosudan.sd/api/cap/rss.xml</link>
    <language>en</language>
    <lastBuildDate>Wed, 06 May 2026 09:34:00 +0000</lastBuildDate>
    <item>
      <title>Above normal Water levels in Blue Nile and White Nile</title>
      <link>https://hydrosudan.sd/api/cap/example-alert.xml</link>
      <description>Above-normal river levels are affecting agricultural lands.</description>
      <pubDate>Wed, 06 May 2026 09:34:00 +0000</pubDate>
      <guid>urn:oid:2.49.0.1.729.1.2026.5.6.9.34.0</guid>
    </item>
  </channel>
</rss>
"""


HYDROSUDAN_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>urn:oid:2.49.0.1.729.1.2026.5.6.9.34.0</identifier>
  <sender>hydrology.sudan@gmail.com</sender>
  <sent>2026-05-06T11:34:00+02:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <category>Transport</category>
    <event>High water</event>
    <responseType>Prepare</responseType>
    <urgency>Immediate</urgency>
    <severity>Moderate</severity>
    <certainty>Observed</certainty>
    <effective>2026-05-06T11:00:00+02:00</effective>
    <onset>2026-05-06T11:30:00+02:00</onset>
    <expires>2026-05-20T11:00:00+02:00</expires>
    <senderName>الادارة العامة لشئون مياه النيل</senderName>
    <headline>High water level in Blue and White Nile</headline>
    <description>Above-normal river levels are affecting agricultural lands.</description>
    <area>
      <areaDesc>Blue Nile</areaDesc>
      <polygon>12.0,33.5 12.0,34.5 14.0,34.5 14.0,33.5 12.0,33.5</polygon>
    </area>
    <area>
      <areaDesc>White Nile</areaDesc>
      <polygon>13.0,31.8 13.0,32.8 15.0,32.8 15.0,31.8 13.0,31.8</polygon>
    </area>
  </info>
</alert>
"""


class HydroSudanSourceTests(unittest.TestCase):
    def test_english_hydrological_cap_routes_and_matches_both_river_polygons(self) -> None:
        source = get_source('hydrosudan')
        assert source is not None
        alert_url = 'https://hydrosudan.sd/api/cap/example-alert.xml'
        responses = {source.url: HYDROSUDAN_FEED, alert_url: HYDROSUDAN_CAP}

        self.assertIn(source, get_alert_sources_for_country('SD'))
        self.assertEqual(source.backend, 'generic_cap')
        self.assertEqual(source.lang, 'en')
        for lat, lon in ((13.0, 34.0), (14.0, 32.3)):
            with self.subTest(lat=lat, lon=lon), patch(
                'wevva_warnings.backends.generic_cap.fetch_text',
                side_effect=lambda url, **_: responses[url],
            ) as fetch_text:
                alerts = get_alerts_for_point(lat, lon, 'SD', lang='en')

            self.assertEqual(
                [alert.id for alert in alerts],
                ['urn:oid:2.49.0.1.729.1.2026.5.6.9.34.0'],
            )
            self.assertEqual(alerts[0].event, 'High water')
            self.assertEqual(alerts[0].area_names, ['Blue Nile', 'White Nile'])
            self.assertEqual(alerts[0].geometry['type'], 'MultiPolygon')
            self.assertEqual(alerts[0].url, alert_url)
            self.assertEqual(
                [call.args[0] for call in fetch_text.call_args_list],
                [source.url, alert_url],
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
