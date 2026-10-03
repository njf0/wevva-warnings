"""Tests for Somalia's National Meteorological Agency source."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


SOMALIA_FEED = """\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Latest alerts from Somalia National Meteorological Agency</title>
    <link>https://meteosomalia.so/api/cap/rss.xml</link>
    <language>en</language>
    <lastBuildDate>Tue, 05 May 2026 09:07:00 +0000</lastBuildDate>
    <item>
      <title>Thunderstorms with Heavy Rainfall Expected in Southern Somalia</title>
      <link>https://meteosomalia.so/api/cap/example-alert.xml</link>
      <description>Heavy rainfall accompanied by thunderstorms is expected.</description>
      <pubDate>Tue, 05 May 2026 09:07:00 +0000</pubDate>
      <guid>urn:oid:2.49.0.1.706.123.2026.5.5.9.7.0</guid>
    </item>
  </channel>
</rss>
"""


SOMALIA_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>urn:oid:2.49.0.1.706.123.2026.5.5.9.7.0</identifier>
  <sender>Forecast.section@moecc.gov.so</sender>
  <sent>2026-05-05T12:07:00+03:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <category>Met</category>
    <event>Rain/Wet Spell</event>
    <responseType>Avoid</responseType>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <effective>2026-05-05T09:00:00+03:00</effective>
    <onset>2026-05-05T15:00:00+03:00</onset>
    <expires>2026-05-05T19:00:00+03:00</expires>
    <senderName>Somalia National Meteorological Agency</senderName>
    <headline>Take Action: Heavy Rain and Thunderstorms Expected in Southern Somalia</headline>
    <description>Heavy rainfall accompanied by thunderstorms is expected across southern Somalia.</description>
    <area>
      <areaDesc>Southern Somalia</areaDesc>
      <polygon>2.966423,46.351505 -0.120394,42.680046 0.003954,41.536061 2.795077,41.650665 4.370326,44.429994 2.966423,46.351505</polygon>
    </area>
  </info>
</alert>
"""


class SomaliaSourceTests(unittest.TestCase):
    def test_english_cap_feed_routes_and_matches_native_polygon(self) -> None:
        source = get_source('meteo_somalia')
        assert source is not None
        alert_url = 'https://meteosomalia.so/api/cap/example-alert.xml'
        responses = {source.url: SOMALIA_FEED, alert_url: SOMALIA_CAP}

        self.assertEqual(get_alert_sources_for_country('SO'), [source])
        self.assertEqual(source.backend, 'generic_cap')
        self.assertEqual(source.lang, 'en')
        with patch(
            'wevva_warnings.backends.generic_cap.fetch_text',
            side_effect=lambda url, **_: responses[url],
        ) as fetch_text:
            alerts = get_alerts_for_point(2.0, 43.0, 'SO', lang='en')

        self.assertEqual(
            [alert.id for alert in alerts],
            ['urn:oid:2.49.0.1.706.123.2026.5.5.9.7.0'],
        )
        self.assertEqual(alerts[0].event, 'Rain/Wet Spell')
        self.assertEqual(alerts[0].area_names, ['Southern Somalia'])
        self.assertEqual(alerts[0].geometry['type'], 'Polygon')
        self.assertEqual(alerts[0].url, alert_url)
        self.assertEqual(
            [call.args[0] for call in fetch_text.call_args_list],
            [source.url, alert_url],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
