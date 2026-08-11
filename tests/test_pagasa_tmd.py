"""Tests for current PAGASA and Thai Meteorological Department CAP links."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from wevva_warnings import get_alerts_for_point
from wevva_warnings.backends.tmd import TMDBackend
from wevva_warnings.registry import get_source


PAGASA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Current General Flood Advisory</title>
    <link type="application/cap+xml" href="https://publicalert.pagasa.dost.gov.ph/output/gfa/current.cap"/>
  </entry>
  <entry>
    <title>Cancellation of General Flood Advisory</title>
    <link type="application/cap+xml" href="https://publicalert.pagasa.dost.gov.ph/output/gfa/cancelled.cap"/>
  </entry>
  <entry>
    <title>Provider web page</title>
    <link type="text/html" href="https://publicalert.pagasa.dost.gov.ph/advisories/current"/>
  </entry>
</feed>
"""

PAGASA_CURRENT_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>pagasa-current</identifier>
  <sender>PAGASA-DOST</sender>
  <sent>2026-08-11T09:00:00+08:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <category>Met</category>
    <event>General Flood Advisory</event>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <onset>2026-08-11T09:00:00+08:00</onset>
    <expires>2026-08-12T09:00:00+08:00</expires>
    <headline>General Flood Advisory for Western Visayas</headline>
    <area>
      <areaDesc>Western Visayas</areaDesc>
      <polygon>10.0,122.0 10.0,123.0 11.0,123.0 11.0,122.0 10.0,122.0</polygon>
    </area>
  </info>
</alert>
"""

PAGASA_CANCELLED_CAP = PAGASA_CURRENT_CAP.replace(
    '<identifier>pagasa-current</identifier>',
    '<identifier>pagasa-cancelled</identifier>',
).replace('<msgType>Alert</msgType>', '<msgType>Cancel</msgType>')

TMD_EN_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Current heavy rain warning</title>
      <link>https://www.tmd.go.th/uploads/CAP/en/current.xml</link>
    </item>
    <item>
      <title>Legacy heavy rain warning</title>
      <link>https://www.tmd.go.th/en/api/xml/legacy.xml</link>
    </item>
    <item>
      <title>Weather web page</title>
      <link>https://www.tmd.go.th/en/weather</link>
    </item>
  </channel>
</rss>
"""

TMD_TH_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>คำเตือนฝนตกหนัก</title>
      <link>https://www.tmd.go.th/uploads/CAP/current-th.xml</link>
    </item>
  </channel>
</rss>
"""


def _tmd_cap(identifier: str, event: str) -> str:
    """Return a compact polygonal Thai CAP warning document."""
    return f"""\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>{identifier}</identifier>
  <sender>Thai Meteorological Department</sender>
  <sent>2026-08-11T05:00:00+07:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <category>Met</category>
    <event>{event}</event>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <onset>2026-08-11T06:00:00+07:00</onset>
    <expires>2026-08-11T18:00:00+07:00</expires>
    <headline>{event} warning</headline>
    <area>
      <areaDesc>Central Thailand</areaDesc>
      <polygon>12.5,99.5 12.5,100.5 13.5,100.5 13.5,99.5 12.5,99.5</polygon>
    </area>
  </info>
</alert>
"""


class PAGASAAndTMDTests(unittest.TestCase):
    def test_pagasa_accepts_current_cap_links_and_excludes_cancellations(self) -> None:
        source = get_source('pagasa')
        assert source is not None
        documents = {
            source.url: PAGASA_FEED,
            'https://publicalert.pagasa.dost.gov.ph/output/gfa/current.cap': PAGASA_CURRENT_CAP,
            'https://publicalert.pagasa.dost.gov.ph/output/gfa/cancelled.cap': PAGASA_CANCELLED_CAP,
        }
        events: list[tuple[str, dict[str, object]]] = []

        def fake_fetch_text(url: str, **_: object) -> str:
            return documents[url]

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.query._utc_now', return_value=datetime(2026, 8, 11, 6, 0, tzinfo=UTC)),
        ):
            alerts = get_alerts_for_point(
                10.5,
                122.5,
                'PH',
                active_only=True,
                progress=lambda event, payload: events.append((event, payload)),
            )

        self.assertEqual([alert.id for alert in alerts], ['pagasa-current'])
        self.assertEqual(alerts[0].geometry['type'], 'Polygon')
        self.assertEqual(
            [event for event, _ in events],
            [
                'query_started',
                'sources_total',
                'source_started',
                'alerts_total',
                'alerts_checked',
                'alerts_checked',
                'alerts_total',
                'alerts_checked',
                'source_finished',
                'finished',
            ],
        )
        self.assertEqual(events[3][1], {'source': 'pagasa', 'total': 2, 'phase': 'documents'})
        self.assertEqual(events[-1], ('finished', {'alert_count': 1}))

    def test_tmd_accepts_current_and_legacy_english_cap_paths(self) -> None:
        source = get_source('tmd_en')
        assert source is not None
        documents = {
            source.url: TMD_EN_FEED,
            'https://www.tmd.go.th/uploads/CAP/en/current.xml': _tmd_cap('tmd-current', 'Heavy Rain'),
            'https://www.tmd.go.th/en/api/xml/legacy.xml': _tmd_cap('tmd-legacy', 'Heavy Rain'),
        }

        def fake_fetch_text(url: str, **_: object) -> str:
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = TMDBackend().fetch_alerts(source, lang='en')

        self.assertEqual([alert.id for alert in alerts], ['tmd-current', 'tmd-legacy'])
        self.assertTrue(all(alert.geometry is not None for alert in alerts))
        self.assertTrue(all(alert.geometry['type'] == 'Polygon' for alert in alerts))

    def test_tmd_current_thai_cap_path_matches_a_point(self) -> None:
        source = get_source('tmd_th')
        assert source is not None
        documents = {
            source.url: TMD_TH_FEED,
            'https://www.tmd.go.th/uploads/CAP/current-th.xml': _tmd_cap('tmd-th-current', 'Heavy Rain'),
        }

        def fake_fetch_text(url: str, **_: object) -> str:
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = get_alerts_for_point(13.0, 100.0, 'TH', lang='th')

        self.assertEqual([alert.id for alert in alerts], ['tmd-th-current'])
        self.assertEqual(alerts[0].source, 'tmd_th')


if __name__ == '__main__':
    unittest.main(verbosity=2)
