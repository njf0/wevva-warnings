"""Focused tests for the CMA/NMC tropical-system source."""

from __future__ import annotations

from datetime import timedelta
import unittest
from unittest.mock import patch

from wevva_warnings import TropicalSystem, get_tropical_products, get_tropical_systems_for_source
from wevva_warnings.backends.cma_tropical import CMATropicalBackend
from wevva_warnings.registry import get_source


CMA_LIST = """\
typhoon_jsons_list_default(({"typhoonList":[
  [101,"ALPHA","阿尔法","2601","2601",null,"Example name","start"],
  [102,"BETA","贝塔","2602","2602",null,"Stopped system","stop"],
  [103,"nameless","热带低压","20260003","20260003",20260003,null,"start"]
]}))
"""

CMA_ALPHA_DETAIL = """\
typhoon_jsons_view_101({"typhoon":[
  101,"ALPHA","阿尔法",2601,2601,null,"Example name","start",
  [
    [1001,"202608110300",1786417200000,"TS",120.1,19.5,985,23,"WNW",18,[["30KTS",200,150,120,180,1001]],{"BABJ":[[12,"202608110300",119.1,20.0,980,25,"BABJ","STS"]]}],
    [1002,"202608110600",1786428000000,"TY",120.6,20.0,975,35,"NW",15,[["30KTS",250,200,150,200,1002],["50KTS",80,60,50,70,1002]],{"BABJ":[[12,"202608110600",119.5,20.5,970,38,"BABJ","TY"]]}]
  ]
]})
"""

CMA_DEPRESSION_DETAIL = """\
typhoon_jsons_view_103({"typhoon":[
  103,"nameless","热带低压",20260003,20260003,20260003,null,"start",
  [[1003,"202608110600",1786428000000,"TD",110.0,12.0,1004,15,"W",20,[],{}]]
]})
"""

CMA_ALPHA_ANALYSIS_ONLY_DETAIL = CMA_ALPHA_DETAIL.replace(
    '{"BABJ":[[12,"202608110600",119.5,20.5,970,38,"BABJ","TY"]]}',
    '{}',
)

CMA_ALPHA_PARTIAL_DETAIL = CMA_ALPHA_DETAIL.replace(
    '[["30KTS",250,200,150,200,1002],["50KTS",80,60,50,70,1002]]',
    '[["30KTS",250,"bad",-1,null,1002],["invalid",80,60,50,70,1002],["64KTS",null,null,null,null,1002]]',
).replace(
    '[[12,"202608110600",119.5,20.5,970,38,"BABJ","TY"]]',
    '[[null,"202608110600",119.5,20.5,970,38,"BABJ","TY"]]',
)

CMA_CEMPAKA_ACTIVE_LIST = """\
typhoon_jsons_list_default(({"typhoonList":[
  [3382203,"CEMPAKA","查帕卡","2632","2632",null,"以其芬芳的花闻名的植物","start"],
  [3368875,"IN-FA","烟花","2631","2631",null,"烟花","stop"]
]}))
"""

CMA_CEMPAKA_ACTIVE_DETAIL = """\
typhoon_jsons_view_3382203({"typhoon":[
  3382203,"CEMPAKA","查帕卡",2632,2632,null,"以其芬芳的花闻名的植物","start",
  [[3382336,"202611070600",1794031200000,"TS",143.2,19.7,995,20,"WNW",27,
    [["30KTS",200,150,150,250,3382336]],
    {"BABJ":[
      [12,"202611070600",140.4,20.9,980,30,"BABJ","STS"],
      [24,"202611070600",137.5,21.8,970,35,"BABJ","TY"],
      [36,"202611070600",135.1,22.7,955,42,"BABJ","STY"],
      [48,"202611070600",134.4,23.4,935,52,"BABJ","SuperTY"],
      [60,"202611070600",135.9,24.0,945,48,"BABJ","STY"],
      [72,"202611070600",138.3,24.5,960,40,"BABJ","TY"],
      [96,"202611070600",144.7,26.4,975,33,"BABJ","TY"],
      [120,"202611070600",152.5,28.6,990,23,"BABJ","TS"]
    ]}
  ]]
]})
"""


class CMATropicalTests(unittest.TestCase):
    def test_active_cempaka_list_detail_and_explicit_babj_leads(self) -> None:
        source = get_source('cma_tropical')
        assert source is not None
        backend = CMATropicalBackend()
        detail_url = 'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_3382203'
        documents = {
            source.url: CMA_CEMPAKA_ACTIVE_LIST,
            detail_url: CMA_CEMPAKA_ACTIVE_DETAIL,
        }

        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            side_effect=lambda url, **_: documents[url],
        ) as fetch_text:
            systems = backend.fetch_tropical_systems(source)

        self.assertEqual([call.args[0] for call in fetch_text.call_args_list], [source.url, detail_url])
        self.assertEqual(len(systems), 1)
        system = systems[0]
        self.assertEqual((system.id, system.name, system.classification), ('2632', 'CEMPAKA', 'Tropical Storm'))
        self.assertEqual((system.center_lat, system.center_lon), (19.7, 143.2))
        self.assertEqual(system.issued_at.isoformat(), '2026-11-07T06:00:00+08:00')
        self.assertEqual(system.max_wind, '20 m/s')
        self.assertEqual(system.min_pressure, '995 hPa')
        self.assertEqual(system.movement, '27 km/h toward WNW')
        self.assertEqual(
            system.parameters['CMA Wind Radii'],
            ['[["30KTS",200,150,150,250,3382336]]'],
        )
        self.assertEqual(set(system.geometries), {'forecast_track'})
        forecast_coordinates = system.geometries['forecast_track']['coordinates']
        self.assertEqual(len(forecast_coordinates), 9)
        self.assertEqual(forecast_coordinates[0], [143.2, 19.7])
        self.assertEqual(forecast_coordinates[-1], [152.5, 28.6])

        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            return_value=CMA_CEMPAKA_ACTIVE_DETAIL,
        ):
            products = get_tropical_products(system)

        self.assertEqual([(product.kind, product.label) for product in products], [('forecast', 'Forecast')])
        data = products[0].data
        assert data is not None
        self.assertEqual(
            data['analysis'],
            {
                'valid_at': '2026-11-07T06:00:00+08:00',
                'wind_radii': [
                    {
                        'threshold': {'value': 30, 'unit': 'KTS'},
                        'radii': {
                            'unit': 'km',
                            'northeast': 200,
                            'southeast': 150,
                            'southwest': 150,
                            'northwest': 250,
                        },
                    }
                ],
            },
        )
        points = data['points']
        self.assertEqual(
            [point['lead_hours'] for point in points],
            [12, 24, 36, 48, 60, 72, 96, 120],
        )
        self.assertTrue(
            all(
                point['forecast_base_at'] == '2026-11-07T06:00:00+08:00'
                for point in points
            )
        )
        self.assertEqual(points[0]['valid_at'], '2026-11-07T18:00:00+08:00')
        self.assertEqual(points[-1]['valid_at'], '2026-11-12T06:00:00+08:00')
        self.assertEqual(set(system.geometries), {'forecast_track'})

    def test_backend_uses_only_current_systems_and_normalizes_latest_analysis(self) -> None:
        source = get_source('cma_tropical')
        assert source is not None
        backend = CMATropicalBackend()
        detail_alpha = 'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_101'
        detail_depression = 'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_103'
        documents = {
            source.url: CMA_LIST,
            detail_alpha: CMA_ALPHA_DETAIL,
            detail_depression: CMA_DEPRESSION_DETAIL,
        }

        def fake_fetch_text(url: str, **_: object) -> str:
            return documents[url]

        with patch('wevva_warnings.backends.cma_tropical.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            systems = backend.fetch_tropical_systems(source)

        self.assertEqual([system.id for system in systems], ['2601', '20260003'])
        self.assertEqual(
            [call.args[0] for call in fetch_text.call_args_list],
            [source.url, detail_alpha, detail_depression],
        )

        system = systems[0]
        self.assertEqual(system.name, 'ALPHA')
        self.assertEqual(system.classification, 'Typhoon')
        self.assertEqual((system.center_lat, system.center_lon), (20.0, 120.6))
        self.assertEqual(system.issued_at.utcoffset(), timedelta(hours=8))
        self.assertEqual(system.issued_at.isoformat(), '2026-08-11T06:00:00+08:00')
        self.assertEqual(system.max_wind, '35 m/s')
        self.assertEqual(system.min_pressure, '975 hPa')
        self.assertEqual(system.movement, '15 km/h toward NW')
        self.assertEqual(system.url, 'https://typhoon.nmc.cn/web.html?tid=101')
        self.assertEqual(system.data_urls, {'cma_tropical_cyclone_detail': detail_alpha})
        self.assertEqual(system.parameters['CMA Tropical Cyclone Number'], ['2601'])
        self.assertEqual(system.parameters['CMA Chinese Name'], ['阿尔法'])
        self.assertEqual(system.parameters['CMA Classification Code'], ['TY'])
        self.assertEqual(
            system.parameters['CMA Wind Radii'],
            ['[["30KTS",250,200,150,200,1002],["50KTS",80,60,50,70,1002]]'],
        )
        self.assertEqual(system.parameters['CMA Forecast Agencies'], ['BABJ'])
        self.assertEqual(
            system.geometries['observed_track'],
            {
                'type': 'LineString',
                'coordinates': [[120.1, 19.5], [120.6, 20.0]],
            },
        )
        self.assertEqual(
            system.geometries['forecast_track'],
            {
                'type': 'LineString',
                'coordinates': [[120.6, 20.0], [119.5, 20.5]],
            },
        )
        self.assertEqual(set(system.geometries), {'observed_track', 'forecast_track'})

        depression = systems[1]
        self.assertEqual(depression.name, '热带低压')
        self.assertEqual(depression.classification, 'Tropical Depression')
        self.assertEqual(depression.geometries, {})

    def test_public_query_attaches_cma_source_info_and_ignores_bad_detail(self) -> None:
        source = get_source('cma_tropical')
        assert source is not None
        documents = {
            source.url: CMA_LIST,
            'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_101': CMA_ALPHA_DETAIL,
            'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_103': 'not a JSONP payload',
        }

        def fake_fetch_text(url: str, **_: object) -> str:
            return documents[url]

        with patch('wevva_warnings.backends.cma_tropical.fetch_text', side_effect=fake_fetch_text):
            systems = get_tropical_systems_for_source('cma_tropical')

        self.assertEqual(len(systems), 1)
        self.assertIs(systems[0].source_info, source)
        self.assertEqual(systems[0].source_info.issuer_country_code, 'CN')

    def test_product_query_exposes_current_babj_forecast_without_text_fabrication(self) -> None:
        source = get_source('cma_tropical')
        assert source is not None
        detail_url = 'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_101'
        documents = {
            source.url: CMA_LIST,
            detail_url: CMA_ALPHA_DETAIL,
            'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_103': CMA_DEPRESSION_DETAIL,
        }

        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            side_effect=lambda url, **_: documents[url],
        ):
            system = get_tropical_systems_for_source('cma_tropical')[0]

        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            return_value=CMA_ALPHA_DETAIL,
        ) as fetch_product:
            products = get_tropical_products(system)

        fetch_product.assert_called_once_with(
            detail_url,
            headers={'Accept': 'application/javascript, application/json, text/plain'},
            debug=False,
        )
        self.assertEqual([(product.kind, product.label) for product in products], [('forecast', 'Forecast')])
        self.assertIsNone(products[0].content)
        self.assertEqual(products[0].content_format, 'markdown')
        self.assertEqual(
            products[0].data,
            {
                'agency': 'BABJ',
                'analysis': {
                    'valid_at': '2026-08-11T06:00:00+08:00',
                    'wind_radii': [
                        {
                            'threshold': {'value': 30, 'unit': 'KTS'},
                            'radii': {
                                'unit': 'km',
                                'northeast': 250,
                                'southeast': 200,
                                'southwest': 150,
                                'northwest': 200,
                            },
                        },
                        {
                            'threshold': {'value': 50, 'unit': 'KTS'},
                            'radii': {
                                'unit': 'km',
                                'northeast': 80,
                                'southeast': 60,
                                'southwest': 50,
                                'northwest': 70,
                            },
                        },
                    ],
                },
                'points': [
                    {
                        'latitude': 20.5,
                        'longitude': 119.5,
                        'lead_hours': 12,
                        'forecast_base_at': '2026-08-11T06:00:00+08:00',
                        'valid_at': '2026-08-11T18:00:00+08:00',
                        'minimum_pressure_hpa': 970,
                        'maximum_wind_mps': 38,
                        'classification': 'Typhoon',
                        'classification_code': 'TY',
                    }
                ],
            },
        )
        self.assertEqual(set(system.geometries), {'observed_track', 'forecast_track'})

    def test_product_query_handles_analysis_only_and_partial_structured_values(self) -> None:
        source = get_source('cma_tropical')
        assert source is not None
        detail_url = 'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_101'
        documents = {
            source.url: CMA_LIST,
            detail_url: CMA_ALPHA_DETAIL,
            'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_103': CMA_DEPRESSION_DETAIL,
        }
        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            side_effect=lambda url, **_: documents[url],
        ):
            system = get_tropical_systems_for_source('cma_tropical')[0]

        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            return_value=CMA_ALPHA_ANALYSIS_ONLY_DETAIL,
        ):
            products = get_tropical_products(system)

        self.assertEqual([(product.kind, product.label) for product in products], [('analysis', 'Analysis')])
        data = products[0].data
        assert data is not None
        self.assertEqual(set(data), {'analysis'})
        self.assertEqual(data['analysis']['valid_at'], '2026-08-11T06:00:00+08:00')
        self.assertEqual(len(data['analysis']['wind_radii']), 2)

        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            return_value=CMA_ALPHA_PARTIAL_DETAIL,
        ):
            products = get_tropical_products(system)

        self.assertEqual([(product.kind, product.label) for product in products], [('forecast', 'Forecast')])
        data = products[0].data
        assert data is not None
        self.assertEqual(
            data['analysis']['wind_radii'],
            [
                {
                    'threshold': {'value': 30, 'unit': 'KTS'},
                    'radii': {'unit': 'km', 'northeast': 250},
                }
            ],
        )
        point = data['points'][0]
        self.assertEqual(point['forecast_base_at'], '2026-08-11T06:00:00+08:00')
        self.assertNotIn('lead_hours', point)
        self.assertNotIn('valid_at', point)
        self.assertEqual(set(system.geometries), {'observed_track', 'forecast_track'})

        depression = TropicalSystem(
            id='20260003',
            source='cma_tropical',
            classification='Tropical Depression',
            name='热带低压',
            headline='Tropical Depression: 热带低压',
            data_urls={'cma_tropical_cyclone_detail': detail_url},
        )
        with patch(
            'wevva_warnings.backends.cma_tropical.fetch_text',
            return_value=CMA_DEPRESSION_DETAIL,
        ):
            self.assertEqual(get_tropical_products(depression), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
