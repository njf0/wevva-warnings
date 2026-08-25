"""Focused tests for HKO and Météo-France La Réunion tropical sources."""

from __future__ import annotations

from datetime import UTC, datetime
from xml.etree import ElementTree
import unittest
from unittest.mock import patch

from wevva_warnings import get_tropical_products, get_tropical_systems_for_source
from wevva_warnings.backends.meteofrance_reunion_tropical import (
    MeteoFranceReunionTropicalBackend,
    _current_season,
)
from wevva_warnings.registry import get_source


HKO_LIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<TropicalCycloneList>
  <TropicalCyclone>
    <TropicalCycloneID>2601</TropicalCycloneID>
    <TropicalCycloneChineseName>薔薇</TropicalCycloneChineseName>
    <TropicalCycloneEnglishName>ROSE</TropicalCycloneEnglishName>
    <TropicalCycloneURL>http://www.weather.gov.hk/wxinfo/currwx/hko_tctrack_2601.xml</TropicalCycloneURL>
  </TropicalCyclone>
</TropicalCycloneList>
"""

HKO_TRACK = """\
<?xml version="1.0" encoding="UTF-8"?>
<TropicalCycloneTrack tcid="2601">
  <BulletinHeader>
    <BulletinName>Tropical Cyclone Track</BulletinName>
    <BulletinType>R</BulletinType>
    <BulletinProvider>Hong Kong Observatory</BulletinProvider>
    <BulletinTime>2026-08-11T20:26:41+08:00</BulletinTime>
  </BulletinHeader>
  <WeatherReport>
    <TropicalCycloneName>ROSE</TropicalCycloneName>
    <PastInformation>
      <Intensity>Typhoon</Intensity>
      <MaximumWind>120km/h</MaximumWind>
      <Time>2026-08-11T00:00:00+00:00</Time>
      <Latitude>14.0N</Latitude>
      <Longitude>120.0E</Longitude>
    </PastInformation>
    <PastInformation>
      <Time>2026-08-11T06:00:00+00:00</Time>
      <Latitude>15.0N</Latitude>
      <Longitude>121.0E</Longitude>
    </PastInformation>
    <AnalysisInformation>
      <Intensity>Severe Tropical Storm</Intensity>
      <MaximumWind>95km/h</MaximumWind>
      <Time>2026-08-11T12:00:00+00:00</Time>
      <Latitude>16.0N</Latitude>
      <Longitude>122.0E</Longitude>
    </AnalysisInformation>
    <ForecastInformation>
      <Latitude>16.2N</Latitude>
      <Longitude>122.2E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Latitude>16.5N</Latitude>
      <Longitude>122.6E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Latitude>16.8N</Latitude>
      <Longitude>122.9E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Latitude>17.2N</Latitude>
      <Longitude>123.3E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Latitude>17.6N</Latitude>
      <Longitude>123.7E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Index>24</Index>
      <Time>2026-08-12T12:00:00+00:00</Time>
      <Latitude>18.0N</Latitude>
      <Longitude>124.0E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Index>48</Index>
      <Time>2026-08-13T12:00:00+00:00</Time>
      <Latitude>19.0N</Latitude>
      <Longitude>126.0E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Index>72</Index>
      <Time>2026-08-14T12:00:00+00:00</Time>
      <Latitude>20.0N</Latitude>
      <Longitude>128.0E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Index>96</Index>
      <Time>2026-08-15T12:00:00+00:00</Time>
      <Latitude>21.0N</Latitude>
      <Longitude>130.0E</Longitude>
    </ForecastInformation>
    <ForecastInformation>
      <Index>120</Index>
      <Time>2026-08-16T12:00:00+00:00</Time>
      <Latitude>22.0N</Latitude>
      <Longitude>132.0E</Longitude>
    </ForecastInformation>
  </WeatherReport>
</TropicalCycloneTrack>
"""

REUNION_LISTING = {
    'cyclone_id': 'SWI$04/20262027',
    'cyclone_name': 'ALEX',
    'current': True,
    'reference_time': '2026-12-14T12:00:00Z',
}

REUNION_TRAJECTORY = {
    'cyclone_trajectory': {
        'cyclone_id': 'SWI$04/20262027',
        'cyclone_name': 'ALEX',
        'season': 20262027,
        'reference_time': '2026-12-14T12:00:00Z',
        'update_time': '2026-12-14T12:25:00Z',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'data_type': 'analysis',
                    'time': '2026-12-14T06:00:00Z',
                    'position_accuracy': 40,
                    'cyclone_data': {
                        'development': 'tropical_storm',
                        'minimum_pressure': 990,
                        'storm_motion': {'speed_kt': 8, 'direction_toward': 270},
                        'maximum_wind': {'wind_speed_kt': 50, 'wind_speed_gust_kt': 65},
                    },
                },
                'geometry': {'type': 'Point', 'coordinates': [62.0, -14.0]},
            },
            {
                'type': 'Feature',
                'properties': {
                    'data_type': 'analysis',
                    'time': '2026-12-14T12:00:00Z',
                    'position_accuracy': 30,
                    'cyclone_data': {
                        'development': 'severe_tropical_storm',
                        'minimum_pressure': 975,
                        'storm_motion': {'speed_kt': 12, 'direction_toward': 280},
                        'maximum_wind': {
                            'wind_speed_kt': 60,
                            'wind_speed_gust_kt': 75,
                        },
                        'wind_contours': [{'wind_speed_kt': 34, 'radius_nm': {'NE': 80}}],
                    },
                },
                'geometry': {'type': 'Point', 'coordinates': [60.0, -15.0]},
            },
            {
                'type': 'Feature',
                'properties': {
                    'data_type': 'forecast',
                    'time': '2026-12-14T18:00:00Z',
                    'cyclone_data': {
                        'development': 'tropical_cyclone',
                        'maximum_wind': {
                            'wind_speed_kt': 75,
                            'wind_speed_gust_kt': 90,
                        },
                    },
                },
                'geometry': {'type': 'Point', 'coordinates': [58.0, -16.0]},
            },
        ],
    }
}


class HKOTropicalTests(unittest.TestCase):
    def test_public_source_query_separates_timed_forecast_fixes_from_curve(self) -> None:
        source = get_source('hko_tropical')
        assert source is not None

        with (
            patch(
                'wevva_warnings.backends.hko.fetch_feed_root',
                return_value=ElementTree.fromstring(HKO_LIST),
            ),
            patch('wevva_warnings.backends.hko.fetch_text', return_value=HKO_TRACK) as fetch_text,
        ):
            systems = get_tropical_systems_for_source('hko_tropical')

        self.assertEqual(len(systems), 1)
        system = systems[0]
        self.assertEqual(system.id, '2601')
        self.assertEqual(system.source, 'hko_tropical')
        self.assertIs(system.source_info, source)
        self.assertEqual(system.source_info.issuer_country_code, 'HK')
        self.assertEqual(system.name, 'ROSE')
        self.assertEqual(system.classification, 'Severe Tropical Storm')
        self.assertEqual((system.center_lat, system.center_lon), (16.0, 122.0))
        self.assertEqual(system.max_wind, '95km/h')
        self.assertEqual(system.issued_at, datetime(2026, 8, 11, 12, 26, 41, tzinfo=UTC))
        self.assertEqual(system.parameters['HKO Chinese Name'], ['薔薇'])
        self.assertEqual(system.parameters['HKO Bulletin Type'], ['R'])
        self.assertEqual(system.parameters['HKO Peak Intensity'], ['Typhoon'])
        self.assertEqual(system.parameters['HKO Peak Maximum Wind'], ['120km/h'])
        self.assertEqual(system.parameters['HKO Peak Time'], ['2026-08-11T00:00:00+00:00'])
        self.assertEqual(
            system.geometries['observed_track']['coordinates'],
            [[120.0, 14.0], [121.0, 15.0], [122.0, 16.0]],
        )
        self.assertEqual(
            system.geometries['forecast_track']['coordinates'],
            [
                [124.0, 18.0],
                [126.0, 19.0],
                [128.0, 20.0],
                [130.0, 21.0],
                [132.0, 22.0],
            ],
        )
        self.assertEqual(set(system.geometries), {'observed_track', 'forecast_track'})
        self.assertEqual(
            fetch_text.call_args.args[0],
            'https://www.weather.gov.hk/wxinfo/currwx/hko_tctrack_2601.xml',
        )

        with patch('wevva_warnings.backends.hko.fetch_text', return_value=HKO_TRACK):
            products = get_tropical_products(system)

        self.assertEqual([(product.kind, product.label) for product in products], [('forecast', 'Forecast')])
        self.assertEqual(
            products[0].data,
            {
                'points': [
                    {
                        'latitude': 18.0,
                        'longitude': 124.0,
                        'valid_at': '2026-08-12T12:00:00+00:00',
                    },
                    {
                        'latitude': 19.0,
                        'longitude': 126.0,
                        'valid_at': '2026-08-13T12:00:00+00:00',
                    },
                    {
                        'latitude': 20.0,
                        'longitude': 128.0,
                        'valid_at': '2026-08-14T12:00:00+00:00',
                    },
                    {
                        'latitude': 21.0,
                        'longitude': 130.0,
                        'valid_at': '2026-08-15T12:00:00+00:00',
                    },
                    {
                        'latitude': 22.0,
                        'longitude': 132.0,
                        'valid_at': '2026-08-16T12:00:00+00:00',
                    },
                ]
            },
        )


class MeteoFranceReunionTropicalTests(unittest.TestCase):
    def test_public_source_query_uses_latest_analysis_not_forecast(self) -> None:
        source = get_source('meteofrance_reunion_tropical')
        assert source is not None
        with patch(
            'wevva_warnings.backends.meteofrance_reunion_tropical._fetch_current_reunion_payloads',
            return_value=[(REUNION_LISTING, REUNION_TRAJECTORY)],
        ):
            systems = get_tropical_systems_for_source('meteofrance_reunion_tropical')

        self.assertEqual(len(systems), 1)
        system = systems[0]
        self.assertIs(system.source_info, source)
        self.assertEqual(system.source_info.issuer_country_code, 'RE')
        self.assertEqual(system.id, 'SWI$04/20262027')
        self.assertEqual(system.name, 'ALEX')
        self.assertEqual(system.classification, 'Severe Tropical Storm')
        self.assertEqual((system.center_lat, system.center_lon), (-15.0, 60.0))
        self.assertEqual(system.issued_at, datetime(2026, 12, 14, 12, 0, tzinfo=UTC))
        self.assertEqual(system.movement, '12 kt toward 280°')
        self.assertEqual(system.min_pressure, '975 hPa')
        self.assertEqual(system.max_wind, '60 kt (gust 75 kt)')
        self.assertEqual(system.geometries['track']['coordinates'][-1], [58.0, -16.0])
        self.assertEqual(system.parameters['Météo-France Position Accuracy'], ['30 km'])
        self.assertEqual(
            system.parameters['Météo-France Forecast Peak'],
            ['Tropical Cyclone, 75 kt (gust 90 kt) at 2026-12-14T18:00:00Z'],
        )
        self.assertEqual(
            system.parameters['Météo-France Wind Contours'],
            ['[{"wind_speed_kt":34,"radius_nm":{"NE":80}}]'],
        )

        with patch(
            'wevva_warnings.backends.meteofrance_reunion_tropical._fetch_reunion_trajectory',
            return_value=REUNION_TRAJECTORY,
        ) as fetch_trajectory:
            products = get_tropical_products(system)

        fetch_trajectory.assert_called_once_with(system.id, debug=False)
        self.assertEqual(
            [(product.kind, product.label) for product in products],
            [('analysis', 'Analysis'), ('forecast', 'Forecast')],
        )
        self.assertEqual(products[0].data['cyclone_data']['development'], 'severe_tropical_storm')
        self.assertEqual(products[1].data['points'][0]['time'], '2026-12-14T18:00:00Z')

    def test_current_season_follows_southwest_indian_ocean_season_boundary(self) -> None:
        self.assertEqual(_current_season(datetime(2026, 1, 1, tzinfo=UTC)), '20252026')
        self.assertEqual(_current_season(datetime(2026, 7, 1, tzinfo=UTC)), '20262027')

    def test_empty_current_list_returns_no_systems(self) -> None:
        source = get_source('meteofrance_reunion_tropical')
        assert source is not None
        with patch(
            'wevva_warnings.backends.meteofrance_reunion_tropical._fetch_current_reunion_payloads',
            return_value=[],
        ):
            self.assertEqual(MeteoFranceReunionTropicalBackend().fetch_tropical_systems(source), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
