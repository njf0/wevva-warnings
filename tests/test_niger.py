"""Tests for Niger's Direction de la Météorologie Nationale source."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


NIGER_FEED = """\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Latest alerts from Direction Nationale de la Météorologie du Niger</title>
    <link>https://www.niger-meteo.ne/api/cap/rss.xml</link>
    <language>en</language>
    <lastBuildDate>Thu, 06 Jun 2024 11:00:00 +0000</lastBuildDate>
    <item>
      <title>Dense poussière en suspension sur l'Aïr le 06/06/2024</title>
      <link>https://www.niger-meteo.ne/api/cap/example-alert.xml</link>
      <description>Dense poussière en suspension réduisant la visibilité.</description>
      <pubDate>Thu, 06 Jun 2024 11:00:00 +0000</pubDate>
      <guid>urn:oid:2.49.0.1.562.0.2024.6.6.11.0.0</guid>
    </item>
  </channel>
</rss>
"""


NIGER_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>urn:oid:2.49.0.1.562.0.2024.6.6.11.0.0</identifier>
  <sender>www.meteo-niger.org</sender>
  <sent>2024-06-06T12:00:00+01:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>fr</language>
    <category>Met</category>
    <event>Tempête de poussière/tempête de sable</event>
    <responseType>Shelter</responseType>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Observed</certainty>
    <effective>2024-06-06T12:00:00+01:00</effective>
    <onset>2024-06-06T12:00:00+01:00</onset>
    <expires>2024-06-07T12:00:00+01:00</expires>
    <senderName>Direction de la Météorologie Nationale du Niger</senderName>
    <headline>Dense poussière en suspension sur l'Aïr</headline>
    <description>Dense poussière en suspension réduisant la visibilité à 200 mètres.</description>
    <area>
      <areaDesc>Aïr, Tahoua, Tillabéri, Niamey, Maradi et Zinder.</areaDesc>
      <polygon>20.513509,7.117137 20.688124,8.687213 19.153593,10.583739 17.085311,11.096734 15.698401,11.11228 14.888689,10.412741 14.392353,9.0603 14.060845,7.692313 14.151304,6.650778 14.286926,5.733605 14.588013,5.018522 14.482679,4.179075 13.683549,3.448446 13.42664,2.096005 14.106079,0.945653 15.068894,1.116651 15.293936,2.904361 15.41386,3.526173 15.563667,3.728262 16.668791,4.241256 19.124221,4.272347 19.461683,5.857968 20.513509,7.117137</polygon>
    </area>
  </info>
</alert>
"""


class NigerSourceTests(unittest.TestCase):
    def test_french_cap_feed_routes_and_matches_native_polygon(self) -> None:
        source = get_source('niger_meteo')
        assert source is not None
        alert_url = 'https://www.niger-meteo.ne/api/cap/example-alert.xml'
        responses = {source.url: NIGER_FEED, alert_url: NIGER_CAP}

        self.assertEqual(get_alert_sources_for_country('NE'), [source])
        self.assertEqual(source.backend, 'generic_cap')
        self.assertEqual(source.lang, 'fr')
        with patch(
            'wevva_warnings.backends.generic_cap.fetch_text',
            side_effect=lambda url, **_: responses[url],
        ) as fetch_text:
            alerts = get_alerts_for_point(16.0, 6.0, 'NE', lang='fr')

        self.assertEqual(
            [alert.id for alert in alerts],
            ['urn:oid:2.49.0.1.562.0.2024.6.6.11.0.0'],
        )
        self.assertEqual(alerts[0].event, 'Tempête de poussière/tempête de sable')
        self.assertEqual(
            alerts[0].area_names,
            ['Aïr', 'Tahoua', 'Tillabéri', 'Niamey', 'Maradi et Zinder.'],
        )
        self.assertEqual(alerts[0].geometry['type'], 'Polygon')
        self.assertEqual(alerts[0].url, alert_url)
        self.assertEqual(
            [call.args[0] for call in fetch_text.call_args_list],
            [source.url, alert_url],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
