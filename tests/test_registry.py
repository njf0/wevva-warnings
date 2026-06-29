"""Sanity checks for the built-in source registry."""

from __future__ import annotations

import unittest

from wevva_warnings.registry import BACKENDS, get_source, list_sources, list_tropical_sources


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

            if source.url is not None:
                self.assertTrue(source.url.startswith(('http://', 'https://')))

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
            {'nhc_gis_atlantic', 'nhc_gis_eastern_pacific', 'cphc_gis_central_pacific', 'jma_tropical'},
        )
        self.assertTrue(all(source.kind == 'tropical_system' for source in tropical_sources))
        self.assertTrue(all(source.kind == 'tropical_system' for source in list_sources(kind='tropical_system')))
        self.assertTrue(all(source.kind == 'alert' for source in list_sources(kind='alert')))

if __name__ == '__main__':
    unittest.main(verbosity=2)
