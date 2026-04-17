"""Tests for high-level source routing and point queries."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch
import warnings

from wevva_warnings.query import get_alerts_for_point, get_alerts_for_source
from wevva_warnings.registry import (
    LanguageNotSupportedError,
    UnsupportedCountryError,
    get_sources_for_country,
)

FMI_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>FMI Warnings</title>
    <item>
      <title>Wind warning</title>
      <link>https://alerts.fmi.fi/cap/alert/fmi-demo.xml</link>
    </item>
  </channel>
</rss>
"""

FMI_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>fmi-demo</identifier>
  <info>
    <language>fi-FI</language>
    <event>Tuulivaroitus</event>
    <headline>Suomenkielinen otsikko</headline>
    <severity>Moderate</severity>
    <description>Suomenkielinen kuvaus.</description>
    <area>
      <areaDesc>Suomi</areaDesc>
      <polygon>60.15,24.85 60.15,25.05 60.30,25.05 60.30,24.85 60.15,24.85</polygon>
    </area>
  </info>
  <info>
    <language>en-GB</language>
    <event>Wind warning</event>
    <headline>English headline</headline>
    <severity>Moderate</severity>
    <description>English description.</description>
    <area>
      <areaDesc>Finland</areaDesc>
      <polygon>60.15,24.85 60.15,25.05 60.30,25.05 60.30,24.85 60.15,24.85</polygon>
    </area>
  </info>
</alert>
"""

TC_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TCI CAP Feed EN</title>
    <language>en</language>
    <item>
      <title>Severe Thunderstorm Watch</title>
      <link>https://cap-sources.s3.amazonaws.com/tc-gov-en/2026-03-18-21-52-34.xml</link>
    </item>
  </channel>
</rss>
"""

TC_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>tc-demo-circle</identifier>
  <info>
    <language>en</language>
    <event>Thunderstorm Watch</event>
    <headline>Severe Thunderstorm Watch for TCI [March 19, 2026]</headline>
    <severity>Moderate</severity>
    <area>
      <areaDesc>Turks and Caicos Islands</areaDesc>
      <circle>21.5757,-71.7792 94</circle>
    </area>
  </info>
</alert>
"""

METSERVICE_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>MetService CAP</title>
    <item>
      <title>Future heavy rain warning</title>
      <link>https://alerts.metservice.com/cap/future.xml</link>
    </item>
  </channel>
</rss>
"""

METSERVICE_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>future-demo</identifier>
  <info>
    <language>en</language>
    <event>Heavy rain</event>
    <headline>Future heavy rain warning</headline>
    <severity>Moderate</severity>
    <effective>2026-03-13T10:00:00+00:00</effective>
    <expires>2026-03-13T18:00:00+00:00</expires>
    <description>Heavy rain is expected tomorrow.</description>
    <area>
      <areaDesc>New Zealand</areaDesc>
      <polygon>-41.50,172.00 -41.50,173.00 -41.00,173.00 -41.00,172.00 -41.50,172.00</polygon>
    </area>
  </info>
</alert>
"""


def fake_fetch_text(url: str, **_: object) -> str:
    """Return canned fixture content for a test URL.

    Parameters
    ----------
    url : str
        URL to fetch from the fixture map.

    Returns
    -------
    str
        XML content associated with the URL.

    """
    documents = {
        'https://alerts.fmi.fi/cap/feed/rss_en-GB.rss': FMI_FEED,
        'https://alerts.fmi.fi/cap/feed/rss_fi-FI.rss': FMI_FEED,
        'https://alerts.fmi.fi/cap/feed/rss_sv-FI.rss': FMI_FEED,
        'https://alerts.fmi.fi/cap/alert/fmi-demo.xml': FMI_CAP,
        'https://cap-sources.s3.amazonaws.com/tc-gov-en/rss.xml': TC_FEED,
        'https://cap-sources.s3.amazonaws.com/tc-gov-en/2026-03-18-21-52-34.xml': TC_CAP,
        'https://alerts.metservice.com/cap/rss': METSERVICE_FEED,
        'https://alerts.metservice.com/cap/future.xml': METSERVICE_CAP,
    }
    return documents[url]


class QueryTests(unittest.TestCase):
    def test_get_sources_for_country_defaults_to_english_source(self) -> None:
        sources = get_sources_for_country('FI')

        self.assertEqual([source.id for source in sources], ['fmi_en'])

    def test_get_sources_for_country_accepts_requested_language(self) -> None:
        sources = get_sources_for_country('FI', lang='fi-FI')

        self.assertEqual([source.id for source in sources], ['fmi_fi'])

    def test_get_sources_for_country_raises_for_unsupported_language(self) -> None:
        with self.assertRaises(LanguageNotSupportedError):
            get_sources_for_country('FI', lang='de')

    def test_get_alerts_for_point_warns_and_falls_back_for_unsupported_language(self) -> None:
        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter('always')
            alerts = get_alerts_for_point(60.22, 24.94, 'FI', lang='de')

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].source, 'fmi_en')
        self.assertEqual(alerts[0].headline, 'English headline')
        self.assertEqual(len(caught), 1)

    def test_get_alerts_for_point_filters_by_polygon_geometry(self) -> None:
        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            matching = get_alerts_for_point(60.22, 24.94, 'FI')
            missing = get_alerts_for_point(61.00, 26.00, 'FI')

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].headline, 'English headline')
        self.assertEqual(missing, [])

    def test_get_alerts_for_point_supports_circle_geometry(self) -> None:
        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = get_alerts_for_point(21.5757, -71.7792, 'TC')

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].source, 'tci_en')
        self.assertEqual(alerts[0].headline, 'Severe Thunderstorm Watch for TCI [March 19, 2026]')

    def test_get_alerts_for_source_active_only_filters_future_alerts(self) -> None:
        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.query._utc_now', return_value=datetime(2026, 3, 12, 22, 0, tzinfo=UTC)),
        ):
            alerts = get_alerts_for_source('metservice_nz', active_only=True)

        self.assertEqual(alerts, [])

    def test_get_alerts_for_point_raises_for_unknown_country(self) -> None:
        with self.assertRaises(UnsupportedCountryError):
            get_alerts_for_point(0.0, 0.0, 'ZZ')

    def test_get_alerts_for_source_returns_empty_for_unknown_source(self) -> None:
        self.assertEqual(get_alerts_for_source('missing'), [])
