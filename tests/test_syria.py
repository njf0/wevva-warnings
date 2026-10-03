"""Tests for Syria's Ministry of Emergency and Disaster Management source."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings import get_alert_sources_for_country, get_alerts_for_point
from wevva_warnings.registry import get_source


SYRIA_FEED = """\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>أحدث التنبيهات من وزارة الطوارئ وإدارة الكوارث</title>
    <link>https://climweb.med.gov.sy/api/cap/rss.xml</link>
    <lastBuildDate>Fri, 02 Oct 2026 19:22:00 +0000</lastBuildDate>
    <item>
      <title>تنبيه جوي: تشكل الضباب وانخفاض مدى الرؤية</title>
      <link>https://climweb.med.gov.sy/api/cap/fixture.xml</link>
      <pubDate>Fri, 02 Oct 2026 19:22:00 +0000</pubDate>
      <guid>urn:oid:2.49.0.1.760.1.fixture</guid>
    </item>
  </channel>
</rss>
"""


SYRIA_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>2.49.0.1.760.1.fixture</identifier>
  <sender>mhews@med.gov.sy</sender>
  <sent>2026-10-02T19:22:00+00:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>ar</language>
    <category>Met</category>
    <event>ضباب</event>
    <urgency>Future</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <onset>2026-10-03T21:00:00+03:00</onset>
    <expires>2026-10-04T07:00:00+03:00</expires>
    <headline>تشكل الضباب وانخفاض مدى الرؤية</headline>
    <area>
      <areaDesc>أجزاء من ادلب وحمص وحماة وريف دمشق الشمالي والغربي</areaDesc>
      <polygon>34.5,36.0 34.5,37.0 35.5,37.0 35.5,36.0 34.5,36.0</polygon>
      <polygon>33.0,35.5 33.0,36.0 33.5,36.0 33.5,35.5 33.0,35.5</polygon>
    </area>
  </info>
</alert>
"""


class SyriaSourceTests(unittest.TestCase):
    def test_arabic_cap_feed_routes_and_matches_native_polygons(self) -> None:
        source = get_source('med_syria')
        assert source is not None
        alert_url = 'https://climweb.med.gov.sy/api/cap/fixture.xml'
        responses = {source.url: SYRIA_FEED, alert_url: SYRIA_CAP}

        with patch(
            'wevva_warnings.backends.generic_cap.fetch_text',
            side_effect=lambda url, **_: responses[url],
        ) as fetch_text:
            alerts = get_alerts_for_point(35.0, 36.5, 'SY', lang='ar')

        self.assertEqual(get_alert_sources_for_country('SY'), [source])
        self.assertEqual(source.backend, 'generic_cap')
        self.assertEqual(source.lang, 'ar')
        self.assertEqual([alert.id for alert in alerts], ['2.49.0.1.760.1.fixture'])
        self.assertEqual(alerts[0].event, 'ضباب')
        self.assertEqual(
            alerts[0].area_names,
            ['أجزاء من ادلب وحمص وحماة وريف دمشق الشمالي والغربي'],
        )
        self.assertEqual(alerts[0].geometry['type'], 'MultiPolygon')
        self.assertEqual(alerts[0].url, alert_url)
        self.assertEqual(
            [call.args[0] for call in fetch_text.call_args_list],
            [source.url, alert_url],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
