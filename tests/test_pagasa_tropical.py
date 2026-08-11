"""Focused tests for the PAGASA tropical-system source."""

from __future__ import annotations

from datetime import timedelta
import unittest
from unittest.mock import patch

from wevva_warnings import get_tropical_systems_for_source
from wevva_warnings.backends.pagasa_tropical import PAGASATropicalBackend
from wevva_warnings.registry import get_source


PAGASA_ACTIVE_HTML = """\
<!doctype html>
<html><body>
  <h2>Tropical Cyclone Bulletin #1</h2>
  <h3>Tropical Depression MAYMAY</h3>
  <p>Issued at 11:00 PM, 04 August 2026</p>
  <p>Valid for broadcast until the next bulletin at 2:00 AM tomorrow.</p>
  <h3>THE LOW PRESSURE AREA WEST OF LA UNION HAS DEVELOPED INTO TROPICAL DEPRESSION “MAYMAY”.</h3>
  <h4>Location of Center (10:00 PM)</h4>
  <p>The center of Tropical Depression MAYMAY was estimated based on all available data at 130 km West Northwest of Bacnotan, La Union (17.0°N, 119.2°E).</p>
  <h4>Intensity</h4>
  <p>Maximum sustained winds of 55 km/h near the center, gustiness of up to 70 km/h, and central pressure of 1000 hPa.</p>
  <h4>Present Movement</h4>
  <p>East northeastward at 10 km/h</p>
  <h4>Extent of Tropical Cyclone Winds</h4>
  <p>Strong winds extend outwards up to 180 km from the center.</p>
</body></html>
"""

PAGASA_INACTIVE_HTML = """\
<!doctype html>
<html><body>
  <h3>No Active Tropical Cyclone within the Philippine Area of Responsibility</h3>
  <a href="https://pubfiles.pagasa.dost.gov.ph/tamss/weather/bulletin/TCB%231_maymay.pdf">TCB#1_maymay.pdf</a>
</body></html>
"""


class PAGASATropicalTests(unittest.TestCase):
    def test_public_query_normalizes_current_bulletin(self) -> None:
        source = get_source('pagasa_tropical')
        assert source is not None

        with patch('wevva_warnings.backends.pagasa_tropical.fetch_text', return_value=PAGASA_ACTIVE_HTML):
            systems = get_tropical_systems_for_source('pagasa_tropical')

        self.assertEqual(len(systems), 1)
        system = systems[0]
        self.assertIs(system.source_info, source)
        self.assertEqual(system.source_info.issuer_country_code, 'PH')
        self.assertEqual(system.id, 'PAGASA-MAYMAY-2026')
        self.assertEqual(system.name, 'MAYMAY')
        self.assertEqual(system.classification, 'Tropical Depression')
        self.assertEqual((system.center_lat, system.center_lon), (17.0, 119.2))
        self.assertEqual(system.issued_at.isoformat(), '2026-08-04T23:00:00+08:00')
        self.assertEqual(system.issued_at.utcoffset(), timedelta(hours=8))
        self.assertEqual(system.advisory_number, '1')
        self.assertEqual(system.movement, 'East northeastward at 10 km/h')
        self.assertEqual(system.max_wind, '55 km/h (gust 70 km/h)')
        self.assertEqual(system.min_pressure, '1000 hPa')
        self.assertEqual(
            system.parameters['PAGASA Tropical Cyclone Wind Extent'],
            ['Strong winds extend outwards up to 180 km from the center.'],
        )
        self.assertEqual(system.data_urls, {'tropical_cyclone_bulletin': source.url})

    def test_inactive_page_does_not_turn_archive_bulletins_into_current_systems(self) -> None:
        source = get_source('pagasa_tropical')
        assert source is not None
        with patch('wevva_warnings.backends.pagasa_tropical.fetch_text', return_value=PAGASA_INACTIVE_HTML):
            self.assertEqual(PAGASATropicalBackend().fetch_tropical_systems(source), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
