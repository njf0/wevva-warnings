"""Tests for Uganda's Department of Meteorological Services source."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


UGANDA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>DMS WIDS — Uganda Early Warning Alerts</title>
  <updated>2026-09-21T06:50:09+03:00</updated>
  <id>https://wids.mwe.go.ug/api/v1/cap/feed</id>
  <language>en-UG</language>
  <entry>
    <title>Thunderstorms over central Uganda</title>
    <id>WIDS-UG-20260921-34-WATCH</id>
    <updated>2026-09-21T06:47:43+03:00</updated>
    <link rel="related" type="application/cap+xml"
          href="https://wids.mwe.go.ug/api/v1/cap/34"/>
    <link rel="alternate" type="text/html"
          href="https://wids.mwe.go.ug/portal/alerts/34"/>
  </entry>
</feed>
"""


UGANDA_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>WIDS-UG-20260921-34-WATCH</identifier>
  <sender>meteo@mwe.go.ug</sender>
  <sent>2026-09-21T06:47:43+03:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en-UG</language>
    <category>Met</category>
    <event>Thunderstorm Warning</event>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <onset>2026-09-21T06:30:00+03:00</onset>
    <expires>2026-09-22T06:30:00+03:00</expires>
    <headline>Thunderstorms over central Uganda</headline>
    <area>
      <areaDesc>Alert area</areaDesc>
      <polygon>0.0,32.0 0.0,33.0 1.0,33.0 1.0,32.0 0.0,32.0</polygon>
      <geocode><valueName>ISO3166-2</valueName><value>UG</value></geocode>
    </area>
  </info>
  <info>
    <language>sw-UG</language>
    <category>Met</category>
    <event>Onyo la Radi</event>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <onset>2026-09-21T06:30:00+03:00</onset>
    <expires>2026-09-22T06:30:00+03:00</expires>
    <headline>Onyo la radi katika Uganda ya kati</headline>
    <area>
      <areaDesc>Eneo la tahadhari</areaDesc>
      <polygon>0.0,32.0 0.0,33.0 1.0,33.0 1.0,32.0 0.0,32.0</polygon>
      <geocode><valueName>ISO3166-2</valueName><value>UG</value></geocode>
    </area>
  </info>
  <info>
    <language>lg-UG</language>
    <category>Met</category>
    <event>Okumenyeeza Enkuba ne Mmugumo</event>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <onset>2026-09-21T06:30:00+03:00</onset>
    <expires>2026-09-22T06:30:00+03:00</expires>
    <headline>Okumenyeeza enkuba ne mmugumo mu masekkati ga Uganda</headline>
    <area>
      <areaDesc>Ekitundu ekirabuddwa</areaDesc>
      <polygon>0.0,32.0 0.0,33.0 1.0,33.0 1.0,32.0 0.0,32.0</polygon>
      <geocode><valueName>ISO3166-2</valueName><value>UG</value></geocode>
    </area>
  </info>
</alert>
"""


class UgandaSourceTests(unittest.TestCase):
    def test_multilingual_cap_blocks_route_and_match_native_polygon(self) -> None:
        source = get_source('uganda_dms')
        assert source is not None
        alert_url = 'https://wids.mwe.go.ug/api/v1/cap/34'
        responses = {source.url: UGANDA_FEED, alert_url: UGANDA_CAP}
        expected_events = {
            'en': 'Thunderstorm Warning',
            'sw': 'Onyo la Radi',
            'lg': 'Okumenyeeza Enkuba ne Mmugumo',
        }

        self.assertEqual(get_alert_sources_for_country('UG'), [source])
        self.assertEqual(source.backend, 'generic_cap')
        self.assertEqual(source.lang, 'en,sw,lg')
        for language, expected_event in expected_events.items():
            with self.subTest(language=language), patch(
                'wevva_warnings.backends.generic_cap.fetch_text',
                side_effect=lambda url, **_: responses[url],
            ) as fetch_text:
                alerts = get_alerts_for_point(0.5, 32.5, 'UG', lang=language)

            self.assertEqual([alert.id for alert in alerts], ['WIDS-UG-20260921-34-WATCH'])
            self.assertEqual(alerts[0].event, expected_event)
            self.assertEqual(alerts[0].geometry['type'], 'Polygon')
            self.assertEqual(alerts[0].geocodes, {'ISO3166-2': ['UG']})
            self.assertEqual(alerts[0].url, alert_url)
            self.assertEqual(
                [call.args[0] for call in fetch_text.call_args_list],
                [source.url, alert_url],
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
