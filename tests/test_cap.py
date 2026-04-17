"""Tests for CAP parsing helpers."""

from __future__ import annotations

import unittest

from wevva_warnings.cap import parse_cap_alert
from wevva_warnings.geometry import point_in_geometry
MULTILINGUAL_CAP = """\
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
      <polygon>60.0,24.0 60.0,25.0 61.0,25.0 61.0,24.0 60.0,24.0</polygon>
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
      <polygon>60.0,24.0 60.0,25.0 61.0,25.0 61.0,24.0 60.0,24.0</polygon>
    </area>
  </info>
</alert>
"""

CIRCLE_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>tc-demo-circle</identifier>
  <info>
    <language>en</language>
    <event>Thunderstorm Watch</event>
    <headline>Severe Thunderstorm Watch for TCI</headline>
    <severity>Moderate</severity>
    <area>
      <areaDesc>Turks and Caicos Islands</areaDesc>
      <circle>21.5757,-71.7792 94</circle>
    </area>
  </info>
</alert>
"""

AREA_GEOCODE_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>dwd-demo</identifier>
  <info>
    <language>en</language>
    <event>Wind warning</event>
    <headline>DWD headline</headline>
    <severity>Moderate</severity>
    <area>
      <areaDesc>polygonal event area</areaDesc>
      <polygon>54.8,8.4 54.8,8.8 55.1,8.8 55.1,8.4 54.8,8.4</polygon>
      <geocode>
        <valueName>EXCLUDE_POLYGON</valueName>
        <value>54.75,8.27 54.80,8.30 54.75,8.27</value>
      </geocode>
      <altitude>0.0</altitude>
      <ceiling>9842.5</ceiling>
    </area>
    <area>
      <areaDesc>Nordfriesische Küste</areaDesc>
      <geocode>
        <valueName>WARNCELLID</valueName>
        <value>501000005</value>
      </geocode>
    </area>
  </info>
</alert>
"""

PARAMETERS_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>parameters-demo</identifier>
  <info>
    <language>en</language>
    <event>Heavy Rain</event>
    <headline>Heavy Rain Warning</headline>
    <severity>Moderate</severity>
    <parameter>
      <valueName>ColourCode</valueName>
      <value>Orange</value>
    </parameter>
    <parameter>
      <valueName>ChanceOfUpgrade</valueName>
      <value>Minimal</value>
    </parameter>
    <area>
      <areaDesc>Example District</areaDesc>
      <polygon>60.0,24.0 60.0,25.0 61.0,25.0 61.0,24.0 60.0,24.0</polygon>
    </area>
  </info>
</alert>
"""


class CAPParserTests(unittest.TestCase):
    def test_parse_cap_alert_defaults_to_english_when_available(self) -> None:
        parsed = parse_cap_alert(MULTILINGUAL_CAP, source='fmi')

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event, 'Wind warning')
        self.assertEqual(parsed.headline, 'English headline')
        self.assertEqual(parsed.area_names, ['Finland'])
        self.assertEqual(parsed.geocodes, {})
        self.assertIsNotNone(parsed.geometry)

    def test_parse_cap_alert_prefers_requested_language(self) -> None:
        parsed = parse_cap_alert(MULTILINGUAL_CAP, source='fmi', preferred_lang='fi-FI')

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event, 'Tuulivaroitus')
        self.assertEqual(parsed.headline, 'Suomenkielinen otsikko')

    def test_parse_cap_alert_preserves_document_url(self) -> None:
        parsed = parse_cap_alert(
            MULTILINGUAL_CAP,
            source='fmi',
            url='https://alerts.fmi.fi/cap/alert/fmi-demo.xml',
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.url, 'https://alerts.fmi.fi/cap/alert/fmi-demo.xml')

    def test_parse_cap_alert_converts_circle_to_matching_polygon(self) -> None:
        parsed = parse_cap_alert(CIRCLE_CAP, source='tc')

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertIsNotNone(parsed.geometry)
        assert parsed.geometry is not None
        self.assertEqual(parsed.geometry['type'], 'Polygon')
        self.assertTrue(point_in_geometry(21.5757, -71.7792, parsed.geometry))
        self.assertFalse(point_in_geometry(25.0, -71.7792, parsed.geometry))

    def test_parse_cap_alert_preserves_structured_areas_and_geocodes(self) -> None:
        parsed = parse_cap_alert(AREA_GEOCODE_CAP, source='dwd')

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.area_names, ['polygonal event area', 'Nordfriesische Küste'])
        self.assertEqual(
            parsed.geocodes,
            {
                'EXCLUDE_POLYGON': ['54.75,8.27 54.80,8.30 54.75,8.27'],
                'WARNCELLID': ['501000005'],
            },
        )
        self.assertIsNotNone(parsed.geometry)

    def test_parse_cap_alert_preserves_structured_parameters(self) -> None:
        parsed = parse_cap_alert(PARAMETERS_CAP, source='demo')

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(
            parsed.parameters,
            {
                'ColourCode': ['Orange'],
                'ChanceOfUpgrade': ['Minimal'],
            },
        )
