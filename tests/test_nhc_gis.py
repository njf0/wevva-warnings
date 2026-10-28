"""Focused NHC/CPHC GIS fallback and forecast-fix regression tests."""

from __future__ import annotations

import io
from pathlib import Path
import unittest
from unittest.mock import call, patch
import zipfile

from wevva_warnings import get_tropical_products
from wevva_warnings.backends.base import BackendError
from wevva_warnings.backends.nhc_gis import NHCGISBackend
from wevva_warnings.registry import get_source


FIXTURES = Path(__file__).parent / 'data' / 'nhc'


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


def _kmz(kml: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('doc.kml', kml)
    return output.getvalue()


TRACK_KMZ = _kmz(_fixture('track-discrete-points.kml'))
AREA_KMZ = _kmz(
    """\
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><Polygon>
  <outerBoundaryIs><LinearRing><coordinates>
    -74,24 -68,24 -68,30 -74,30 -74,24
  </coordinates></LinearRing></outerBoundaryIs>
</Polygon></Placemark></Document></kml>
"""
)


class NHCGISFallbackTests(unittest.TestCase):
    def test_explicit_rss_asset_links_remain_preferred(self) -> None:
        source = get_source('nhc_gis_atlantic')
        assert source is not None
        explicit_urls = {
            'forecast_track': 'https://www.nhc.noaa.gov/gis/explicit/AL042026_TRACK.kmz',
            'cone': 'https://www.nhc.noaa.gov/gis/explicit/AL042026_CONE.kmz',
            'watch_warning': 'https://www.nhc.noaa.gov/gis/explicit/AL042026_WW.kmz',
        }

        with (
            patch(
                'wevva_warnings.backends._cap_feed.fetch_text',
                return_value=_fixture('rss-explicit-assets.xml'),
            ),
            patch(
                'wevva_warnings.backends.nhc_gis.fetch_bytes',
                side_effect=lambda url, **_: TRACK_KMZ if url.endswith('TRACK.kmz') else AREA_KMZ,
            ) as fetch_asset,
        ):
            systems = NHCGISBackend().fetch_tropical_systems(source)

        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].data_urls, explicit_urls)
        self.assertEqual(
            [request.args[0] for request in fetch_asset.call_args_list],
            list(explicit_urls.values()),
        )
        self.assertFalse(any('_latest.kmz' in request.args[0] for request in fetch_asset.call_args_list))

    def test_summary_only_entries_use_current_assets_for_multiple_valid_basins(self) -> None:
        examples = (
            ('nhc_gis_atlantic', 'rss-summary-only-atlantic.xml', 'AL052026'),
            ('cphc_gis_central_pacific', 'rss-summary-only-central-pacific.xml', 'CP022026'),
        )

        for source_id, fixture_name, atcf in examples:
            source = get_source(source_id)
            assert source is not None

            def fake_fetch_bytes(url: str, **_: object) -> bytes:
                return TRACK_KMZ if url.endswith('_TRACK_latest.kmz') else AREA_KMZ

            with self.subTest(source=source_id):
                with (
                    patch(
                        'wevva_warnings.backends._cap_feed.fetch_text',
                        return_value=_fixture(fixture_name),
                    ),
                    patch(
                        'wevva_warnings.backends.nhc_gis.fetch_bytes',
                        side_effect=fake_fetch_bytes,
                    ) as fetch_asset,
                ):
                    systems = NHCGISBackend().fetch_tropical_systems(source)

            self.assertEqual(len(systems), 1)
            system = systems[0]
            root = 'https://www.nhc.noaa.gov/storm_graphics/api'
            expected_urls = {
                'forecast_track': f'{root}/{atcf}_TRACK_latest.kmz',
                'cone': f'{root}/{atcf}_CONE_latest.kmz',
                'watch_warning': f'{root}/{atcf}_WW_latest.kmz',
            }
            self.assertEqual(system.data_urls, expected_urls)
            self.assertEqual(
                [request.args[0] for request in fetch_asset.call_args_list],
                list(expected_urls.values()),
            )
            self.assertEqual(set(system.geometries), {'forecast_track', 'cone', 'watch_warning'})

    def test_missing_or_malformed_fallback_assets_do_not_remove_summary(self) -> None:
        source = get_source('nhc_gis_atlantic')
        assert source is not None

        def unavailable(url: str, **_: object) -> bytes:
            if url.endswith('_TRACK_latest.kmz'):
                return b'not a KMZ or KML document'
            raise BackendError('optional current asset unavailable')

        with (
            patch(
                'wevva_warnings.backends._cap_feed.fetch_text',
                return_value=_fixture('rss-summary-only-atlantic.xml'),
            ),
            patch('wevva_warnings.backends.nhc_gis.fetch_bytes', side_effect=unavailable),
        ):
            systems = NHCGISBackend().fetch_tropical_systems(source)

        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].id, 'al052026')
        self.assertEqual(systems[0].name, 'BRAVO')
        self.assertEqual(systems[0].geometries, {})
        self.assertEqual(set(systems[0].data_urls), {'forecast_track', 'cone', 'watch_warning'})

    def test_cross_basin_or_malformed_atcf_ids_cannot_build_current_asset_urls(self) -> None:
        source = get_source('cphc_gis_central_pacific')
        assert source is not None
        feeds = (
            _fixture('rss-summary-only-atlantic.xml'),
            _fixture('rss-summary-only-central-pacific.xml')
            .replace('CP022026', 'CP002026')
            .replace('cp022026', 'cp002026'),
        )

        for feed in feeds:
            with self.subTest(feed=feed[:80]):
                with (
                    patch('wevva_warnings.backends._cap_feed.fetch_text', return_value=feed),
                    patch('wevva_warnings.backends.nhc_gis.fetch_bytes') as fetch_asset,
                ):
                    systems = NHCGISBackend().fetch_tropical_systems(source)

            self.assertEqual(systems, [])
            fetch_asset.assert_not_called()


class NHCGISForecastFixTests(unittest.TestCase):
    def test_discrete_points_replace_presentation_lines_and_expose_only_explicit_leads(self) -> None:
        source = get_source('nhc_gis_atlantic')
        assert source is not None

        def fake_fetch_bytes(url: str, **_: object) -> bytes:
            return TRACK_KMZ if url.endswith('_TRACK_latest.kmz') else AREA_KMZ

        with (
            patch(
                'wevva_warnings.backends._cap_feed.fetch_text',
                return_value=_fixture('rss-summary-only-atlantic.xml'),
            ),
            patch('wevva_warnings.backends.nhc_gis.fetch_bytes', side_effect=fake_fetch_bytes),
        ):
            systems = NHCGISBackend().fetch_tropical_systems(source)

        system = systems[0]
        self.assertEqual(
            system.geometries['forecast_track'],
            {
                'type': 'LineString',
                'coordinates': [
                    [-70.0, 25.0],
                    [-71.0, 26.0],
                    [-71.5, 26.5],
                    [-72.0, 27.0],
                    [-73.0, 28.0],
                ],
                'bbox': [-73.0, 25.0, -70.0, 28.0],
            },
        )
        self.assertNotIn([-70.5, 25.5], system.geometries['forecast_track']['coordinates'])
        self.assertNotIn([-70.75, 25.75], system.geometries['forecast_track']['coordinates'])

        with (
            patch('wevva_warnings.backends.nhc_gis.fetch_text', return_value='<rss/>'),
            patch('wevva_warnings.backends.nhc_gis.fetch_bytes', return_value=TRACK_KMZ) as fetch_track,
        ):
            products = get_tropical_products(system)

        self.assertEqual(fetch_track.call_args_list, [call(system.data_urls['forecast_track'], debug=False)])
        self.assertEqual([(product.kind, product.label) for product in products], [('forecast', 'Forecast')])
        self.assertEqual(
            products[0].data,
            {
                'points': [
                    {'latitude': 26.0, 'longitude': -71.0, 'lead_hours': 12},
                    {'latitude': 27.0, 'longitude': -72.0, 'lead_hours': 24},
                    {'latitude': 28.0, 'longitude': -73.0, 'lead_hours': 36},
                ],
            },
        )
        self.assertNotIn(
            {'latitude': 26.5, 'longitude': -71.5, 'lead_hours': 72},
            products[0].data['points'],  # type: ignore[index]
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
