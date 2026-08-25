"""Sanity checks for the built-in source registry."""

from __future__ import annotations

import unittest

from wevva_warnings.registry import (
    BACKENDS,
    get_source,
    get_sources_for_country,
    list_sources,
    list_tropical_sources,
)


class RegistryTests(unittest.TestCase):
    def test_registry_entries_are_well_formed(self) -> None:
        sources = list_sources()
        ids = [source.id for source in sources]

        self.assertEqual(len(ids), len(set(ids)))

        for source in sources:
            self.assertIs(get_source(source.id), source)
            self.assertIn(source.backend, BACKENDS)

            if source.country_code is not None:
                self.assertEqual(len(source.country_code), 2)
                self.assertEqual(source.country_code, source.country_code.upper())
                self.assertTrue(source.country_code.isalpha())

            if source.issuer_country_code is not None:
                self.assertEqual(len(source.issuer_country_code), 2)
                self.assertEqual(source.issuer_country_code, source.issuer_country_code.upper())
                self.assertTrue(source.issuer_country_code.isalpha())

            if source.display_geography is not None:
                self.assertEqual(source.kind, 'tropical_system')
                self.assertIn(source.display_geography.kind, {'country', 'map_unit', 'subunit'})
                self.assertTrue(source.display_geography.code)
                self.assertTrue(source.display_geography.name)

            for basin, geography in source.basin_display_geographies:
                self.assertEqual(source.kind, 'tropical_system')
                self.assertTrue(basin.strip())
                self.assertIn(geography.kind, {'country', 'map_unit', 'subunit'})
                self.assertTrue(geography.code)

            self.assertNotIn(source.country_code, source.additional_country_codes)
            for country_code in source.additional_country_codes:
                self.assertEqual(len(country_code), 2)
                self.assertEqual(country_code, country_code.upper())
                self.assertTrue(country_code.isalpha())

            if source.url is not None:
                self.assertTrue(source.url.startswith(('ftp://', 'http://', 'https://')))

            if source.lang is not None:
                for part in source.lang.split(','):
                    self.assertTrue(part)
                    self.assertEqual(part, part.strip())
                    self.assertEqual(part, part.lower())

            self.assertIn(source.kind, {'alert', 'tropical_system'})

    def test_tropical_sources_are_explicitly_filterable(self) -> None:
        tropical_sources = list_tropical_sources()
        tropical_ids = {source.id for source in tropical_sources}

        self.assertEqual(
            tropical_ids,
            {
                'nhc_gis_atlantic',
                'nhc_gis_eastern_pacific',
                'cphc_gis_central_pacific',
                'jma_tropical',
                'cma_tropical',
                'pagasa_tropical',
                'bom_tropical',
                'hko_tropical',
                'meteofrance_reunion_tropical',
            },
        )
        self.assertTrue(all(source.kind == 'tropical_system' for source in tropical_sources))
        self.assertTrue(all(source.kind == 'tropical_system' for source in list_sources(kind='tropical_system')))
        self.assertTrue(all(source.kind == 'alert' for source in list_sources(kind='alert')))

    def test_tropical_sources_declare_issuer_country_without_country_routing(self) -> None:
        tropical_sources = {source.id: source for source in list_tropical_sources()}

        self.assertEqual(
            {source_id: source.issuer_country_code for source_id, source in tropical_sources.items()},
            {
                'nhc_gis_atlantic': 'US',
                'nhc_gis_eastern_pacific': 'US',
                'cphc_gis_central_pacific': 'US',
                'jma_tropical': 'JP',
                'cma_tropical': 'CN',
                'pagasa_tropical': 'PH',
                'bom_tropical': 'AU',
                'hko_tropical': 'HK',
                'meteofrance_reunion_tropical': 'RE',
            },
        )
        self.assertTrue(all(source.country_code is None for source in tropical_sources.values()))
        self.assertTrue(all(source.kind == 'alert' for source in get_sources_for_country('US')))

    def test_nws_routes_the_us_and_its_territories_to_one_source(self) -> None:
        expected_codes = {'US', 'AS', 'GU', 'MP', 'PR', 'VI'}

        for country_code in expected_codes:
            with self.subTest(country_code=country_code):
                self.assertEqual(
                    [source.id for source in get_sources_for_country(country_code)],
                    ['nws'],
                )

if __name__ == '__main__':
    unittest.main(verbosity=2)
