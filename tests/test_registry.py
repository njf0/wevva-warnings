"""Sanity checks for the built-in source registry."""

from __future__ import annotations

import unittest

from wevva_warnings.registry import BACKENDS, get_source, list_sources, list_v2_sources


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

    def test_v2_sources_are_explicitly_tracked(self) -> None:
        v2_sources = list_v2_sources()

        self.assertTrue(v2_sources)
        self.assertTrue(all(source.provider_v2 for source in v2_sources))
        self.assertEqual(
            {source.id for source in v2_sources},
            {
                'aemet',
                'anmeteo',
                'bahrain_ar',
                'bahrain_en',
                'bom',
                'belgidromet_en',
                'belgidromet_ru',
                'bmkg_en',
                'bmkg_id',
                'dem_barbados',
                'dma_anguilla',
                'antigua_met',
                'dmh_myanmar',
                'dms_botswana',
                'dwd_de',
                'dwd_en',
                'dirmet_cg',
                'ethiomet',
                'fmi_en',
                'fmi_fi',
                'fmi_sv',
                'geomet',
                'gmet',
                'hydromet_guyana',
                'hydrometcenter_en',
                'hydrometcenter_ru',
                'hko',
                'imd_india',
                'inamhi',
                'inam_mz',
                'igebu',
                'indomet',
                'inmet',
                'inumet',
                'jmd_ar',
                'jmd_en',
                'kazhydromet_en',
                'kazhydromet_ru',
                'kma',
                'kyrgyzhydromet_en',
                'kyrgyzhydromet_ru',
                'metservice_nz',
                'meteocomores',
                'meteodjibouti',
                'meteogambia',
                'meteoguinebissau',
                'cma',
                'meteo_ke',
                'meteo_cameroon_en',
                'meteo_cameroon_fr',
                'meteo_cw_en',
                'meteo_cw_nl',
                'meteo_cw_pap',
                'met_eireann',
                'meteoalarm_atom_andorra',
                'meteoalarm_atom_austria',
                'meteoalarm_atom_belgium',
                'meteoalarm_atom_bosnia_herzegovina',
                'meteoalarm_atom_bulgaria',
                'meteoalarm_atom_croatia',
                'meteoalarm_atom_cyprus',
                'meteoalarm_atom_czechia',
                'meteoalarm_atom_denmark',
                'meteoalarm_atom_estonia',
                'meteoalarm_atom_france',
                'meteoalarm_atom_greece',
                'meteoalarm_atom_hungary',
                'meteoalarm_atom_israel',
                'meteoalarm_atom_italy',
                'meteoalarm_atom_latvia',
                'meteoalarm_atom_lithuania',
                'meteoalarm_atom_luxembourg',
                'meteoalarm_atom_malta',
                'meteoalarm_atom_moldova',
                'meteoalarm_atom_montenegro',
                'meteoalarm_atom_netherlands',
                'meteoalarm_atom_north_macedonia',
                'meteoalarm_atom_poland',
                'meteoalarm_atom_portugal',
                'meteoalarm_atom_romania',
                'meteoalarm_atom_serbia',
                'meteoalarm_atom_slovakia',
                'meteoalarm_atom_slovenia',
                'meteoalarm_atom_sweden',
                'meteoalarm_atom_switzerland',
                'meteoalarm_atom_united_kingdom',
                'meteoalarm_atom_ukraine',
                'meteomauritanie',
                'meteordcongo',
                'meteo_sc',
                'meteosouthsudan',
                'meteosudan',
                'meteotchad',
                'meteochile',
                'meteobenin',
                'meteoburkina',
                'meteoliberia',
                'meteotogo',
                'metmalawi',
                'met_no',
                'msj',
                'mms',
                'dmh_py',
                'namem_en',
                'nms_belize',
                'nws',
                'nve',
                'nimet_en',
                'pagasa',
                'qatar_caa_ar',
                'qatar_caa_en',
                'saint_lucia',
                'slmet',
                'smg',
                'smn',
                'smn_mexico',
                'solomon_met',
                'svg_met',
                'eswatini_met',
                'tma_en',
                'tma_sw',
                'tci_en',
                'tci_es',
                'tci_ht',
                'tmd_en',
                'tmd_th',
                'ttms',
                'uzhydromet_en',
                'uzhydromet_ru',
                'vedur',
                'vmgd',
                'weatherzw',
                'zmd',
            },
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
