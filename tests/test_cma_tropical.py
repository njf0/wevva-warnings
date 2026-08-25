"""Focused tests for the CMA/NMC tropical-system source."""

from __future__ import annotations

from datetime import timedelta
import unittest
from unittest.mock import patch

from wevva_warnings import get_tropical_products, get_tropical_systems_for_source
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


class CMATropicalTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
