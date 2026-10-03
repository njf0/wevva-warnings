"""Tests for Colombia's focused IDEAM warning source."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


IDEAM_MIRROR_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2" version="2.0">
  <channel>
    <pubDate>Fri, 02 Oct 2026 21:11:23 +0000</pubDate>
    <item>
      <link>https://severeweather.wmo.int/v2/cap-alerts/co-ideam-es/2026/10/02/current.xml</link>
      <cap:expires>Sun, 04 Oct 2026 16:00:00 +0000</cap:expires>
    </item>
    <item>
      <link>https://severeweather.wmo.int/v2/cap-alerts/co-ideam-es/2026/10/01/expired.xml</link>
      <cap:expires>Fri, 02 Oct 2026 16:00:00 +0000</cap:expires>
    </item>
    <item>
      <link>https://example.invalid/not-ideam.xml</link>
      <cap:expires>Sun, 04 Oct 2026 16:00:00 +0000</cap:expires>
    </item>
  </channel>
</rss>
"""


IDEAM_CAP_DOCUMENT = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>ideam-fixture</identifier>
  <sender>servicio@ideam.gov.co</sender>
  <sent>2026-10-01T13:04:15-00:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en-CO</language>
    <category>Met</category>
    <event>Forest fire warning</event>
    <urgency>Future</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <onset>2026-10-01T11:00:00-05:00</onset>
    <expires>2026-10-04T11:00:00-05:00</expires>
    <description>Moderate probability of forest fires.</description>
    <area>
      <areaDesc>Belén, Caparrapí</areaDesc>
      <polygon>5.0,-73.5 5.0,-72.5 6.0,-72.5 6.0,-73.5 5.0,-73.5</polygon>
      <polygon>4.0,-75.0 4.0,-74.0 5.0,-74.0 5.0,-75.0 4.0,-75.0</polygon>
    </area>
  </info>
</alert>
"""


class IDEAMTests(unittest.TestCase):
    def test_mirror_filters_history_and_matches_detailed_cap_polygons(self) -> None:
        source = get_source('ideam_colombia')
        assert source is not None
        alert_url = (
            'https://severeweather.wmo.int/v2/cap-alerts/co-ideam-es/'
            '2026/10/02/current.xml'
        )
        responses = {
            source.url: IDEAM_MIRROR_FEED,
            alert_url: IDEAM_CAP_DOCUMENT,
        }

        with patch(
            'wevva_warnings.backends._cap_feed.fetch_text',
            side_effect=lambda url, **_: responses[url],
        ) as fetch_text:
            alerts = get_alerts_for_point(5.5, -73.0, 'CO')

        self.assertEqual(get_alert_sources_for_country('CO'), [source])
        self.assertEqual(source.backend, 'ideam')
        self.assertEqual(source.lang, 'es')
        self.assertEqual([alert.id for alert in alerts], ['ideam-fixture'])
        self.assertEqual(alerts[0].event, 'Forest fire warning')
        self.assertEqual(alerts[0].area_names, ['Belén', 'Caparrapí'])
        self.assertEqual(alerts[0].geometry['type'], 'MultiPolygon')
        self.assertEqual(alerts[0].url, alert_url)
        self.assertEqual(
            [call.args[0] for call in fetch_text.call_args_list],
            [source.url, alert_url],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
