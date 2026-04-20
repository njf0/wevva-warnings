"""Tests for geocode-based geometry resolution."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from wevva_warnings import geocoding
from wevva_warnings import geometry_from_geocodes, get_alerts_for_point, get_alerts_for_source

EMMA_FIXTURE_PATH = Path(__file__).resolve().parent / 'data' / 'emma_geocodes.json'
EMMA_FRAGMENT_FIXTURE_PATH = Path(__file__).resolve().parent / 'data' / 'emma_geocodes'
EMMA_ALIASES_FIXTURE_PATH = Path(__file__).resolve().parent / 'data' / 'emma_aliases.json'
BOM_AMOC_FIXTURE_PATH = Path(__file__).resolve().parent / 'data' / 'bom_amoc_geocodes.json'
BOM_AMOC_FRAGMENT_FIXTURE_PATH = Path(__file__).resolve().parent / 'data' / 'bom_amoc_geocodes'
JMA_AREA_FIXTURE_PATH = Path(__file__).resolve().parent / 'data' / 'jma_area_geocodes'

METEOALARM_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Meteoalarm</title>
  <entry>
    <title>Example warning</title>
    <link type="application/cap+xml" href="https://feeds.meteoalarm.org/api/v1/warnings/feeds-belgium/demo-warning" />
  </entry>
</feed>
"""

METEOALARM_CAP_WITHOUT_GEOMETRY = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>emma-demo</identifier>
  <info>
    <language>en-GB</language>
    <event>Wind warning</event>
    <severity>Moderate</severity>
    <headline>Wind warning for Luxembourg province</headline>
    <description>Wind warning for Luxembourg province.</description>
    <area>
      <areaDesc>Luxembourg</areaDesc>
      <geocode><valueName>EMMA_ID</valueName><value>BE001</value></geocode>
    </area>
  </info>
</alert>
"""

JMA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>https://www.data.jma.go.jp/developer/xml/data/20260418214050_0_VPWW53_200000.xml</id>
    <title>長野県気象警報・注意報</title>
    <link type="application/xml" href="https://www.data.jma.go.jp/developer/xml/data/20260418214050_0_VPWW53_200000.xml"/>
  </entry>
</feed>
"""

JMA_WARNING = """\
<Report xmlns="http://xml.kishou.go.jp/jmaxml1/">
  <Head xmlns="http://xml.kishou.go.jp/jmaxml1/informationBasis1/">
    <Title>長野県気象警報・注意報</Title>
    <ReportDateTime>2026-04-18T21:33:00+09:00</ReportDateTime>
    <Headline>
      <Text>長野県では、乾燥に注意してください。</Text>
    </Headline>
  </Head>
  <Body xmlns="http://xml.kishou.go.jp/jmaxml1/body/meteorology1/">
    <Warning type="気象警報・注意報（市町村等）">
      <Item>
        <Kind>
          <Name>乾燥注意報</Name>
          <Status>発表</Status>
        </Kind>
        <Area>
          <Name>長野市</Name>
          <Code>2020100</Code>
        </Area>
      </Item>
    </Warning>
  </Body>
</Report>
"""


class GeocodingTests(unittest.TestCase):
    def tearDown(self) -> None:
        geocoding._load_emma_index.cache_clear()
        geocoding._load_emma_geometry.cache_clear()
        geocoding._load_emma_aliases.cache_clear()
        geocoding._load_bom_amoc_index.cache_clear()
        geocoding._load_bom_amoc_geometry.cache_clear()
        geocoding._load_jma_area_geometry.cache_clear()

    def test_geometry_from_geocodes_resolves_emma_geometry(self) -> None:
        with patch('wevva_warnings.geocoding._find_emma_dataset_dir', return_value=EMMA_FRAGMENT_FIXTURE_PATH):
            geometry = geometry_from_geocodes({'EMMA_ID': ['BE001']})

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry['type'], 'Polygon')

    def test_geometry_from_geocodes_resolves_nuts3_alias_to_emma_geometry(self) -> None:
        with (
            patch('wevva_warnings.geocoding._find_emma_dataset_path', return_value=EMMA_FIXTURE_PATH),
            patch('wevva_warnings.geocoding._find_emma_aliases_path', return_value=EMMA_ALIASES_FIXTURE_PATH),
        ):
            geometry = geometry_from_geocodes({'NUTS3': ['FR221']})

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry['type'], 'Polygon')

    def test_geometry_from_geocodes_resolves_bom_amoc_geometry(self) -> None:
        with patch('wevva_warnings.geocoding._find_bom_amoc_dataset_dir', return_value=BOM_AMOC_FRAGMENT_FIXTURE_PATH):
            geometry = geometry_from_geocodes({'AMOC-AreaCode': ['WA_MW011']})

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry['type'], 'Polygon')

    def test_geometry_from_geocodes_resolves_bom_me_geometry(self) -> None:
        with patch('wevva_warnings.geocoding._find_bom_amoc_dataset_path', return_value=BOM_AMOC_FIXTURE_PATH):
            geometry = geometry_from_geocodes({'AMOC-AreaCode': ['NSW_ME012']})

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry['type'], 'Polygon')

    def test_geometry_from_geocodes_resolves_bom_pw_geometry(self) -> None:
        with patch('wevva_warnings.geocoding._find_bom_amoc_dataset_path', return_value=BOM_AMOC_FIXTURE_PATH):
            geometry = geometry_from_geocodes({'AMOC-AreaCode': ['WA_PW004']})

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry['type'], 'Polygon')

    def test_geometry_from_geocodes_resolves_jma_area_geometry(self) -> None:
        with patch('wevva_warnings.geocoding._find_jma_area_dataset_dir', return_value=JMA_AREA_FIXTURE_PATH):
            geometry = geometry_from_geocodes({'JMA Area Code': ['2020100']})

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry['type'], 'Polygon')
        self.assertEqual(geometry['bbox'], [138.0, 36.5, 138.6, 36.9])

    def test_get_alerts_for_point_uses_emma_geometry_when_alert_geometry_is_missing(self) -> None:
        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                'https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-belgium': METEOALARM_FEED,
                'https://feeds.meteoalarm.org/api/v1/warnings/feeds-belgium/demo-warning': METEOALARM_CAP_WITHOUT_GEOMETRY,
            }
            return documents[url]

        with (
            patch('wevva_warnings.geocoding._find_emma_dataset_path', return_value=EMMA_FIXTURE_PATH),
            patch('wevva_warnings.backends.meteoalarm_atom.fetch_text', side_effect=fake_fetch_text),
        ):
            matching = get_alerts_for_point(49.8, 5.5, 'BE')
            missing = get_alerts_for_point(51.0, 4.0, 'BE')

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].id, 'emma-demo')
        self.assertIsNotNone(matching[0].geometry)
        self.assertEqual(missing, [])

    def test_get_alerts_for_point_uses_nuts3_alias_to_match_meteoalarm_france(self) -> None:
        meteoalarm_feed = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Meteoalarm</title>
  <entry>
    <title>France warning</title>
    <link type="application/cap+xml" href="https://feeds.meteoalarm.org/api/v1/warnings/feeds-france/demo-warning" />
  </entry>
</feed>
"""
        meteoalarm_cap = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>france-alias-demo</identifier>
  <info>
    <language>en-GB</language>
    <event>Thunderstorm</event>
    <severity>Moderate</severity>
    <headline>France alias warning</headline>
    <description>France alias warning.</description>
    <area>
      <areaDesc>Aisne</areaDesc>
      <geocode><valueName>NUTS3</valueName><value>FR221</value></geocode>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                'https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-france': meteoalarm_feed,
                'https://feeds.meteoalarm.org/api/v1/warnings/feeds-france/demo-warning': meteoalarm_cap,
            }
            return documents[url]

        with (
            patch('wevva_warnings.geocoding._find_emma_dataset_path', return_value=EMMA_FIXTURE_PATH),
            patch('wevva_warnings.geocoding._find_emma_aliases_path', return_value=EMMA_ALIASES_FIXTURE_PATH),
            patch('wevva_warnings.backends.meteoalarm_atom.fetch_text', side_effect=fake_fetch_text),
        ):
            matching = get_alerts_for_point(49.8, 3.5, 'FR')
            missing = get_alerts_for_point(48.5, 2.3, 'FR')

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].id, 'france-alias-demo')
        self.assertIsNotNone(matching[0].geometry)
        self.assertEqual(missing, [])

    def test_get_alerts_for_source_attaches_resolved_geometry(self) -> None:
        meteoalarm_feed = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Meteoalarm</title>
  <entry>
    <title>Romania warning</title>
    <link type="application/cap+xml" href="https://feeds.meteoalarm.org/api/v1/warnings/feeds-romania/demo-warning" />
  </entry>
</feed>
"""
        meteoalarm_cap = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>romania-alias-demo</identifier>
  <info>
    <language>en-GB</language>
    <event>Thunderstorm</event>
    <severity>Moderate</severity>
    <headline>Romania alias warning</headline>
    <description>Romania alias warning.</description>
    <area>
      <areaDesc>Aisne</areaDesc>
      <geocode><valueName>NUTS3</valueName><value>FR221</value></geocode>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                'https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-romania': meteoalarm_feed,
                'https://feeds.meteoalarm.org/api/v1/warnings/feeds-romania/demo-warning': meteoalarm_cap,
            }
            return documents[url]

        with (
            patch('wevva_warnings.geocoding._find_emma_dataset_path', return_value=EMMA_FIXTURE_PATH),
            patch('wevva_warnings.geocoding._find_emma_aliases_path', return_value=EMMA_ALIASES_FIXTURE_PATH),
            patch('wevva_warnings.backends.meteoalarm_atom.fetch_text', side_effect=fake_fetch_text),
        ):
            alerts = get_alerts_for_source('meteoalarm_atom_romania')

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].id, 'romania-alias-demo')
        self.assertIsNotNone(alerts[0].geometry)

    def test_get_alerts_for_point_uses_bom_amoc_geometry_when_cap_geometry_is_missing(self) -> None:
        swic_feed = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>BoM warning</title>
      <link>https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/demo-warning.xml</link>
    </item>
  </channel>
</rss>
"""
        swic_cap = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>bom-amoc-demo</identifier>
  <info>
    <language>en</language>
    <event>Wind</event>
    <headline>Strong Wind Warning</headline>
    <severity>Moderate</severity>
    <area>
      <areaDesc>Western Australia: Leeuwin Coast</areaDesc>
      <geocode><valueName>AMOC-AreaCode</valueName><value>WA_MW011</value></geocode>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                'https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/rss.xml': swic_feed,
                'https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/demo-warning.xml': swic_cap,
            }
            return documents[url]

        with (
            patch('wevva_warnings.geocoding._find_bom_amoc_dataset_path', return_value=BOM_AMOC_FIXTURE_PATH),
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
        ):
            matching = get_alerts_for_point(-34.5, 115.0, 'AU')
            missing = get_alerts_for_point(-31.0, 151.0, 'AU')

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].id, 'bom-amoc-demo')
        self.assertIsNotNone(matching[0].geometry)
        self.assertEqual(missing, [])

    def test_get_alerts_for_point_uses_jma_area_geometry_when_alert_geometry_is_missing(self) -> None:
        feed_url = 'https://www.data.jma.go.jp/developer/xml/feed/extra.xml'
        warning_url = 'https://www.data.jma.go.jp/developer/xml/data/20260418214050_0_VPWW53_200000.xml'

        with (
            patch('wevva_warnings.geocoding._find_jma_area_dataset_dir', return_value=JMA_AREA_FIXTURE_PATH),
            patch('wevva_warnings.backends._cap_feed.fetch_text', return_value=JMA_FEED) as feed_fetch,
            patch('wevva_warnings.backends.jma.fetch_text', return_value=JMA_WARNING) as xml_fetch,
        ):
            matching = get_alerts_for_point(36.7, 138.3, 'JP')
            missing = get_alerts_for_point(35.6, 139.7, 'JP')

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].id, '20260418214050_0_VPWW53_200000')
        self.assertIsNotNone(matching[0].geometry)
        self.assertEqual(missing, [])
        self.assertEqual(feed_fetch.call_count, 2)
        self.assertEqual(xml_fetch.call_count, 2)
        self.assertEqual(feed_fetch.call_args.args[0], feed_url)
        self.assertEqual(xml_fetch.call_args.args[0], warning_url)
