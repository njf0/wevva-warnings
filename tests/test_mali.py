"""Tests for Mali's national meteorological CAP source."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


MALI_FEED = """\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Dernières alertes de Mali Meteo</title>
    <link>https://malimeteo.ml/api/cap/rss.xml</link>
    <language>en</language>
    <lastBuildDate>Wed, 23 Sep 2026 15:09:53 +0000</lastBuildDate>
    <item>
      <title>Orages et pluies dans la majeure partie Sud du pays</title>
      <link>https://malimeteo.ml/api/cap/example-alert.xml</link>
      <description>Des orages accompagnés de pluies sont attendus.</description>
      <pubDate>Wed, 23 Sep 2026 15:09:53 +0000</pubDate>
      <guid>urn:oid:2.49.0.1.466.0.2026.9.23.15.9.53</guid>
    </item>
  </channel>
</rss>
"""


MALI_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>urn:oid:2.49.0.1.466.0.2026.9.23.15.9.53</identifier>
  <sender>malimeteo@malimeteo.ml</sender>
  <sent>2026-09-23T15:09:53.959000-00:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>fr</language>
    <category>Met</category>
    <event>Pluie/période humide</event>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <effective>2026-09-21T15:00:00+00:00</effective>
    <onset>2026-09-23T16:00:00+00:00</onset>
    <expires>2026-09-24T09:00:00+00:00</expires>
    <senderName>MALI-METEO</senderName>
    <headline>Orages et pluies dans la majeure partie Sud du pays</headline>
    <description>Des orages accompagnés de pluies sont attendus en fin de journée.</description>
    <area>
      <areaDesc>La majeure partie Sud du pays.</areaDesc>
      <polygon>10.0,-12.0 10.0,-4.0 16.0,-4.0 16.0,-12.0 10.0,-12.0</polygon>
    </area>
  </info>
</alert>
"""


class MaliSourceTests(unittest.TestCase):
    def test_french_cap_feed_routes_and_matches_native_polygon(self) -> None:
        source = get_source('mali_meteo')
        assert source is not None
        alert_url = 'https://malimeteo.ml/api/cap/example-alert.xml'
        responses = {source.url: MALI_FEED, alert_url: MALI_CAP}

        self.assertEqual(get_alert_sources_for_country('ML'), [source])
        self.assertEqual(source.backend, 'generic_cap')
        self.assertEqual(source.lang, 'fr')
        with patch(
            'wevva_warnings.backends.generic_cap.fetch_text',
            side_effect=lambda url, **_: responses[url],
        ) as fetch_text:
            alerts = get_alerts_for_point(12.64, -8.0, 'ML', lang='fr')

        self.assertEqual(
            [alert.id for alert in alerts],
            ['urn:oid:2.49.0.1.466.0.2026.9.23.15.9.53'],
        )
        self.assertEqual(alerts[0].event, 'Pluie/période humide')
        self.assertEqual(alerts[0].area_names, ['La majeure partie Sud du pays.'])
        self.assertEqual(alerts[0].geometry['type'], 'Polygon')
        self.assertEqual(alerts[0].url, alert_url)
        self.assertEqual(
            [call.args[0] for call in fetch_text.call_args_list],
            [source.url, alert_url],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
