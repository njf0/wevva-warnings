"""Focused tests for named tropical-system grouping and map hints."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from wevva_warnings import (
    CanonicalTropicalSystem,
    get_canonical_tropical_systems,
    group_tropical_systems,
)
from wevva_warnings.models import TropicalSystem
from wevva_warnings.registry import get_source
from wevva_warnings.sources import DisplayGeography, WarningSource


def _system(
    system_id: str,
    source: str,
    name: str,
    **kwargs: object,
) -> TropicalSystem:
    return TropicalSystem(
        id=system_id,
        source=source,
        classification=str(kwargs.pop('classification', 'Tropical Storm')),
        name=name,
        headline=str(kwargs.pop('headline', f'{source} report for {name}')),
        **kwargs,
    )


class TropicalGroupingTests(unittest.TestCase):
    def test_same_name_groups_without_reconciling_source_meteorology(self) -> None:
        jma_track = {'type': 'LineString', 'coordinates': [[155.0, 28.0], [156.0, 29.0]]}
        cma_track = {'type': 'LineString', 'coordinates': [[154.4, 29.0], [155.0, 30.0]]}
        jma = _system(
            'jma-2026-nangka',
            'jma_tropical',
            'NANGKA',
            classification='Typhoon',
            issued_at=datetime(2026, 8, 14, 6, 0, tzinfo=UTC),
            advisory_number='12',
            center_lat=28.0,
            center_lon=155.0,
            movement='NW 15 km/h',
            min_pressure='996 hPa',
            max_wind='35 m/s',
            geometries={'forecast_track': jma_track},
            parameters={'jma_value': ['one']},
        )
        cma = _system(
            'cma-2026-nangka',
            'cma_tropical',
            'Nangka',
            classification='Severe Tropical Storm',
            issued_at=datetime(2026, 8, 14, 5, 0, tzinfo=UTC),
            advisory_number='8',
            center_lat=29.0,
            center_lon=154.4,
            movement='NNW 20 km/h',
            min_pressure='1000 hPa',
            max_wind='30 m/s',
            geometries={'forecast_track': cma_track},
            parameters={'cma_value': ['two']},
        )

        groups = group_tropical_systems([jma, cma])

        self.assertEqual(groups, [CanonicalTropicalSystem(name='NANGKA', observations=[jma, cma])])
        self.assertIs(groups[0].observations[0], jma)
        self.assertIs(groups[0].observations[1], cma)
        self.assertEqual((jma.center_lat, jma.center_lon, jma.min_pressure), (28.0, 155.0, '996 hPa'))
        self.assertEqual((cma.center_lat, cma.center_lon, cma.min_pressure), (29.0, 154.4, '1000 hPa'))
        self.assertIs(jma.geometries['forecast_track'], jma_track)
        self.assertIs(cma.geometries['forecast_track'], cma_track)
        self.assertNotEqual(jma.classification, cma.classification)
        self.assertNotEqual(jma.movement, cma.movement)
        self.assertNotEqual(jma.max_wind, cma.max_wind)
        self.assertNotEqual(jma.issued_at, cma.issued_at)
        self.assertNotEqual(jma.parameters, cma.parameters)

    def test_grouping_normalizes_only_case_and_surrounding_whitespace(self) -> None:
        cma_nangka = _system('cma-nangka', 'cma_tropical', ' nangka ')
        jma_nangka = _system('jma-nangka', 'jma_tropical', 'NANGKA')
        lala = _system('cphc-lala', 'cphc_gis_central_pacific', 'LALA')

        groups = group_tropical_systems([cma_nangka, lala, jma_nangka])

        self.assertEqual([group.name for group in groups], ['nangka', 'LALA'])
        self.assertEqual(groups[0].observations, [cma_nangka, jma_nangka])
        self.assertEqual(groups[1].observations, [lala])

    def test_different_and_unnamed_systems_remain_separate_in_input_order(self) -> None:
        alpha = _system('alpha', 'first', 'ALPHA')
        beta = _system('beta', 'second', 'BETA')
        unnamed_one = _system('unnamed-one', 'first', '')
        unnamed_two = _system('unnamed-two', 'second', '   ')

        groups = group_tropical_systems([alpha, unnamed_one, beta, unnamed_two])

        self.assertEqual([group.name for group in groups], ['ALPHA', '', 'BETA', ''])
        self.assertEqual(
            [group.observations for group in groups],
            [[alpha], [unnamed_one], [beta], [unnamed_two]],
        )

    def test_canonical_fetch_wraps_raw_api_results_without_changing_them(self) -> None:
        raw = [
            _system('first', 'jma_tropical', 'NANGKA'),
            _system('second', 'cma_tropical', 'nangka'),
        ]

        with patch('wevva_warnings.query.get_tropical_systems', return_value=raw) as get_raw:
            groups = get_canonical_tropical_systems(
                source_ids=['jma_tropical', 'cma_tropical'],
                debug=True,
            )

        get_raw.assert_called_once_with(
            source_ids=['jma_tropical', 'cma_tropical'],
            debug=True,
        )
        self.assertEqual(groups[0].observations, raw)
        self.assertIs(groups[0].observations[0], raw[0])
        self.assertIs(groups[0].observations[1], raw[1])

    def test_display_geography_hints_are_explicit_and_do_not_affect_grouping(self) -> None:
        jma_source = get_source('jma_tropical')
        cphc_source = get_source('cphc_gis_central_pacific')
        reunion_source = get_source('meteofrance_reunion_tropical')
        assert jma_source is not None
        assert cphc_source is not None
        assert reunion_source is not None

        self.assertIsNone(jma_source.display_geography)
        self.assertEqual(jma_source.issuer_country_code, 'JP')

        assert cphc_source.display_geography is not None
        self.assertEqual(cphc_source.issuer_country_code, 'US')
        self.assertEqual(cphc_source.display_geography.kind, 'subunit')
        self.assertEqual(cphc_source.display_geography.code, 'US-HI')
        self.assertEqual(cphc_source.display_geography.name, 'Hawaii')

        assert reunion_source.display_geography is not None
        self.assertEqual(reunion_source.issuer_country_code, 'RE')
        self.assertEqual(reunion_source.display_geography.kind, 'map_unit')
        self.assertEqual(reunion_source.display_geography.code, 'RE')
        self.assertEqual(reunion_source.display_geography.name, 'Réunion')

        cphc_observation = _system('cphc-lala', cphc_source.id, 'LALA')
        jma_observation = _system('jma-lala', jma_source.id, 'lala')
        cphc_observation.source_info = cphc_source
        jma_observation.source_info = jma_source

        groups = group_tropical_systems([cphc_observation, jma_observation])

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].observations, [cphc_observation, jma_observation])

    def test_display_geography_resolves_basin_then_source_then_issuer_country(self) -> None:
        eastern_pacific_source = get_source('nhc_gis_eastern_pacific')
        atlantic_source = get_source('nhc_gis_atlantic')
        cphc_source = get_source('cphc_gis_central_pacific')
        jma_source = get_source('jma_tropical')
        assert eastern_pacific_source is not None
        assert atlantic_source is not None
        assert cphc_source is not None
        assert jma_source is not None

        eastern_pacific = _system(
            'ep012026',
            eastern_pacific_source.id,
            'HERNAN',
            basin='Eastern Pacific',
        )
        eastern_pacific.source_info = eastern_pacific_source
        assert eastern_pacific.display_geography is not None
        self.assertEqual(eastern_pacific.display_geography.kind, 'country')
        self.assertEqual(eastern_pacific.display_geography.code, 'US')
        self.assertIsNone(eastern_pacific.display_geography.name)
        self.assertEqual(eastern_pacific_source.issuer_country_code, 'US')

        mismatched_basin = _system(
            'ep-source-atlantic-basin',
            eastern_pacific_source.id,
            'EXAMPLE',
            basin='Atlantic',
        )
        mismatched_basin.source_info = eastern_pacific_source
        assert mismatched_basin.display_geography is not None
        self.assertEqual(mismatched_basin.display_geography.code, 'US')

        atlantic = _system(
            'al012026',
            atlantic_source.id,
            'ALEX',
            basin='Atlantic',
        )
        atlantic.source_info = atlantic_source
        assert atlantic.display_geography is not None
        self.assertEqual(atlantic.display_geography.kind, 'country')
        self.assertEqual(atlantic.display_geography.code, 'US')
        self.assertIsNone(atlantic.display_geography.name)

        central_pacific = _system(
            'cp012026',
            cphc_source.id,
            'LALA',
            basin='Central Pacific',
        )
        central_pacific.source_info = cphc_source
        self.assertIs(central_pacific.display_geography, cphc_source.display_geography)
        assert central_pacific.display_geography is not None
        self.assertEqual(central_pacific.display_geography.code, 'US-HI')
        self.assertEqual(central_pacific.display_geography.name, 'Hawaii')

        ordinary = _system(
            'jma-nangka',
            jma_source.id,
            'NANGKA',
            basin='Northwest Pacific',
        )
        ordinary.source_info = jma_source
        assert ordinary.display_geography is not None
        self.assertEqual(ordinary.display_geography.kind, 'country')
        self.assertEqual(ordinary.display_geography.code, 'JP')
        self.assertIsNone(ordinary.display_geography.name)

    def test_basin_display_geography_precedes_source_wide_hint(self) -> None:
        source_hint = DisplayGeography(kind='subunit', code='US-HI', name='Hawaii')
        basin_hint = DisplayGeography(kind='country', code='MX', name='Mexico')
        source = WarningSource(
            id='example_tropical',
            name='Example Tropical Centre',
            backend='example',
            country_code=None,
            url='https://example.test/tropical',
            kind='tropical_system',
            issuer_country_code='US',
            display_geography=source_hint,
            basin_display_geographies=(('Eastern Pacific', basin_hint),),
        )

        self.assertIs(source.resolve_display_geography(' eastern pacific '), basin_hint)
        self.assertIs(source.resolve_display_geography('Atlantic'), source_hint)
        self.assertIs(source.resolve_display_geography(None), source_hint)


if __name__ == '__main__':
    unittest.main(verbosity=2)
