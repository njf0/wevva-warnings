"""Tests for the command-line interface."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from rich.progress import Progress
from typer.testing import CliRunner

from wevva_warnings.cli import _DebugProgress, app
from wevva_warnings.models import Alert, CanonicalTropicalSystem, TropicalProduct, TropicalSystem
from wevva_warnings.registry import UnsupportedCountryError
from wevva_warnings.sources import DisplayGeography, WarningSource

runner = CliRunner()


class CLITests(unittest.TestCase):
    def test_debug_progress_handles_public_warning_events(self) -> None:
        with Progress(disable=True) as progress:
            debug_progress = _DebugProgress(progress)
            debug_progress.emit('alerts_total', {'source': 'fmi_en', 'total': 2, 'phase': 'documents'})
            debug_progress.emit(
                'alerts_checked',
                {'source': 'fmi_en', 'completed': 1, 'total': 2, 'phase': 'documents'},
            )

            task = progress.tasks[debug_progress.documents_task_id]
            self.assertEqual(task.total, 2)
            self.assertEqual(task.completed, 1)

    def test_point_command_passes_flags(self) -> None:
        with patch('wevva_warnings.cli.get_alerts_for_point', return_value=[]) as get_alerts:
            result = runner.invoke(app, ['point', '40.71', '-74.00', 'DE', '--lang', 'de', '--debug', '--active'])

        self.assertEqual(result.exit_code, 0)
        get_alerts.assert_called_once_with(40.71, -74.0, 'DE', lang='de', debug=True, active_only=True)

    def test_point_command_prints_human_output(self) -> None:
        alert = Alert(
            id='demo',
            source='nws',
            event='Wind Advisory',
            headline='Wind Advisory',
            severity='Moderate',
            description='Strong west winds expected through the afternoon.',
            onset=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
            expires=datetime(2026, 3, 12, 18, 0, tzinfo=UTC),
        )

        with patch('wevva_warnings.cli.get_alerts_for_point', return_value=[alert]):
            result = runner.invoke(app, ['point', '40.71', '-74.00', 'US'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Wind Advisory', result.stdout)
        self.assertIn('Moderate', result.stdout)
        self.assertIn('2026-03-12T12:00:00+00:00', result.stdout)
        self.assertIn('Strong west winds expected', result.stdout)

    def test_point_command_prints_country_error(self) -> None:
        with patch('wevva_warnings.cli.get_alerts_for_point', side_effect=UnsupportedCountryError('ZZ')):
            result = runner.invoke(app, ['point', '49.8', '7.67', 'ZZ'])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("country code 'ZZ'", result.output)

    def test_country_command_passes_flags_and_uses_public_country_api(self) -> None:
        with patch('wevva_warnings.cli.get_alerts_for_country', return_value=[]) as get_alerts:
            result = runner.invoke(app, ['country', 'DE', '--lang', 'de', '--active', '--formatted'])

        self.assertEqual(result.exit_code, 0)
        get_alerts.assert_called_once_with('DE', lang='de', active_only=True)
        self.assertIn('No country-level alert candidates.', result.stdout)

    def test_country_command_prints_country_error(self) -> None:
        with patch('wevva_warnings.cli.get_alerts_for_country', side_effect=UnsupportedCountryError('ZZ')):
            result = runner.invoke(app, ['country', 'ZZ'])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("country code 'ZZ'", result.output)

    def test_source_command_passes_flags(self) -> None:
        source = WarningSource(
            id='fmi_en',
            name='FMI',
            backend='generic_cap',
            country_code='FI',
            url='https://alerts.fmi.fi/cap/feed/rss_en-GB.rss',
            lang='en',
        )

        with (
            patch('wevva_warnings.cli.get_source', return_value=source),
            patch('wevva_warnings.cli.get_alerts_for_source', return_value=[]) as get_alerts,
        ):
            result = runner.invoke(app, ['source', 'fmi_en', '--debug', '--active', '--formatted'])

        self.assertEqual(result.exit_code, 0)
        get_alerts.assert_called_once_with('fmi_en', debug=True, active_only=True)

    def test_source_command_pretty_prints_alert_object_by_default(self) -> None:
        alert = Alert(
            id='demo',
            source='fmi_en',
            event='Wind Warning',
            headline='Wind Warning',
            severity='Moderate',
            description='Strong west winds expected.',
            area_names=['Demo County'],
            geocodes={'WARNCELLID': ['123456']},
            geometry={
                'type': 'Polygon',
                'coordinates': [[[-77.1, 38.8], [-77.0, 38.9], [-76.9, 38.8], [-77.1, 38.8]]],
            },
            onset=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
            expires=datetime(2026, 3, 12, 18, 0, tzinfo=UTC),
        )

        with (
            patch(
                'wevva_warnings.cli.get_source',
                return_value=WarningSource(
                    id='fmi_en',
                    name='FMI',
                    backend='generic_cap',
                    country_code='FI',
                    url='https://alerts.fmi.fi/cap/feed/rss_en-GB.rss',
                    lang='en',
                ),
            ),
            patch('wevva_warnings.cli.get_alerts_for_source', return_value=[alert]),
        ):
            result = runner.invoke(app, ['source', 'fmi_en'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Alert demo', result.stdout)
        self.assertIn('Alert(', result.stdout)
        self.assertIn("headline='Wind Warning'", result.stdout)
        self.assertIn("'WARNCELLID': [", result.stdout)
        self.assertIn("'123456'", result.stdout)
        self.assertIn("'bbox':", result.stdout)
        self.assertNotIn("'headline': 'Wind Warning'", result.stdout)
        self.assertNotIn("'coordinates':", result.stdout)

    def test_source_command_prints_formatted_table_when_requested(self) -> None:
        alert = Alert(
            id='demo',
            source='fmi_en',
            event='Wind Warning',
            headline='Wind Warning',
            severity='Moderate',
            description='Strong west winds expected.',
            onset=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
            expires=datetime(2026, 3, 12, 18, 0, tzinfo=UTC),
        )

        with (
            patch(
                'wevva_warnings.cli.get_source',
                return_value=WarningSource(
                    id='fmi_en',
                    name='FMI',
                    backend='generic_cap',
                    country_code='FI',
                    url='https://alerts.fmi.fi/cap/feed/rss_en-GB.rss',
                    lang='en',
                ),
            ),
            patch('wevva_warnings.cli.get_alerts_for_source', return_value=[alert]),
        ):
            result = runner.invoke(app, ['source', 'fmi_en', '--formatted'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Wind Warning', result.stdout)
        self.assertIn('Moderate', result.stdout)
        self.assertIn('Strong west winds expected.', result.stdout)

    def test_source_command_prints_unknown_source_error(self) -> None:
        with patch('wevva_warnings.cli.get_source', return_value=None):
            result = runner.invoke(app, ['source', 'missing'])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("source is registered with id 'missing'", result.output)

    def test_tropical_source_command_passes_flags(self) -> None:
        source = WarningSource(
            id='nhc_gis_atlantic',
            name='NHC Atlantic',
            backend='nhc_gis',
            country_code=None,
            url='https://www.nhc.noaa.gov/gis-at.xml',
            lang='en',
            kind='tropical_system',
        )

        with (
            patch('wevva_warnings.cli.get_source', return_value=source),
            patch('wevva_warnings.cli.get_tropical_systems_for_source', return_value=[]) as get_systems,
        ):
            result = runner.invoke(app, ['tropical-source', 'nhc_gis_atlantic', '--debug', '--formatted'])

        self.assertEqual(result.exit_code, 0)
        get_systems.assert_called_once_with('nhc_gis_atlantic', debug=True)

    def test_tropical_products_command_fetches_selected_observation_lazily(self) -> None:
        source = WarningSource(
            id='nhc_gis_atlantic',
            name='NHC',
            backend='nhc_gis',
            country_code=None,
            url='https://www.nhc.noaa.gov/gis-at.xml',
            kind='tropical_system',
        )
        system = TropicalSystem(
            id='al012026',
            source=source.id,
            classification='Tropical Storm',
            name='ALPHA',
            headline='Tropical Storm ALPHA',
            source_info=source,
        )
        products = [
            TropicalProduct(
                kind='analysis',
                label='Forecast Discussion',
                title='Tropical Storm Alpha Discussion Number 1',
                content='Official discussion.',
                data={'product_code': 'TCD'},
            )
        ]

        with (
            patch('wevva_warnings.cli.get_source', return_value=source),
            patch('wevva_warnings.cli.get_tropical_systems_for_source', return_value=[system]) as get_systems,
            patch('wevva_warnings.cli.get_tropical_products', return_value=products) as get_products,
        ):
            result = runner.invoke(
                app,
                ['tropical-products', source.id, 'AL012026', '--content'],
            )

        self.assertEqual(result.exit_code, 0)
        get_systems.assert_called_once_with(source.id, debug=False)
        get_products.assert_called_once_with(system, debug=False)
        self.assertIn('ALPHA / NHC', result.stdout)
        self.assertIn('Forecast Discussion', result.stdout)
        self.assertIn('Kind: analysis', result.stdout)
        self.assertIn('Official discussion.', result.stdout)
        self.assertIn('product_code', result.stdout)

    def test_tropical_source_command_pretty_prints_system_by_default(self) -> None:
        system = TropicalSystem(
            id='al012026',
            source='nhc_gis_atlantic',
            classification='Hurricane',
            name='Alex',
            headline='Hurricane Alex Advisory #5',
            basin='Atlantic',
            center_lat=25.4,
            center_lon=-71.2,
            summary='Hurricane Alex remains well offshore.',
            data_urls={'cone': 'https://example.com/cone.kmz'},
        )

        with (
            patch(
                'wevva_warnings.cli.get_source',
                return_value=WarningSource(
                    id='nhc_gis_atlantic',
                    name='NHC Atlantic',
                    backend='nhc_gis',
                    country_code=None,
                    url='https://www.nhc.noaa.gov/gis-at.xml',
                    lang='en',
                    kind='tropical_system',
                ),
            ),
            patch('wevva_warnings.cli.get_tropical_systems_for_source', return_value=[system]),
        ):
            result = runner.invoke(app, ['tropical-source', 'nhc_gis_atlantic'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Tropical System al012026', result.stdout)
        self.assertIn('TropicalSystem(', result.stdout)
        self.assertIn("headline='Hurricane Alex Advisory #5'", result.stdout)
        self.assertIn("'cone':", result.stdout)

    def test_tropical_source_command_prints_formatted_table_when_requested(self) -> None:
        system = TropicalSystem(
            id='al012026',
            source='nhc_gis_atlantic',
            classification='Hurricane',
            name='Alex',
            headline='Hurricane Alex Advisory #5',
            basin='Atlantic',
            center_lat=25.4,
            center_lon=-71.2,
            max_wind='85 kt',
            min_pressure='980 hPa',
            summary='Hurricane Alex remains well offshore.',
            geometries={'cone': {'type': 'Polygon', 'coordinates': []}},
        )

        with (
            patch(
                'wevva_warnings.cli.get_source',
                return_value=WarningSource(
                    id='nhc_gis_atlantic',
                    name='NHC Atlantic',
                    backend='nhc_gis',
                    country_code=None,
                    url='https://www.nhc.noaa.gov/gis-at.xml',
                    lang='en',
                    kind='tropical_system',
                ),
            ),
            patch('wevva_warnings.cli.get_tropical_systems_for_source', return_value=[system]),
        ):
            result = runner.invoke(app, ['tropical-source', 'nhc_gis_atlantic', '--formatted'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Hurricane Alex Advisory', result.output)
        self.assertIn('#5', result.stdout)
        self.assertIn('Hurricane', result.stdout)
        self.assertIn('85 kt', result.stdout)
        self.assertIn('980 hPa', result.stdout)
        self.assertIn('Geometries:', result.stdout)
        self.assertIn('cone', result.stdout)

    def test_tropical_source_command_rejects_alert_sources(self) -> None:
        with patch(
            'wevva_warnings.cli.get_source',
            return_value=WarningSource(
                id='nws',
                name='NWS',
                backend='nws',
                country_code='US',
                url='https://api.weather.gov/alerts/active',
                kind='alert',
            ),
        ):
            result = runner.invoke(app, ['tropical-source', 'nws'])

        self.assertEqual(result.exit_code, 2)
        self.assertIn('not a tropical-system source', result.output)

    def test_tropical_groups_command_shows_default_and_explicit_geography(self) -> None:
        jma_source = WarningSource(
            id='jma_tropical',
            name='Japan Meteorological Agency',
            backend='jma_tropical',
            country_code=None,
            url='https://example.test/jma',
            kind='tropical_system',
            issuer_country_code='JP',
        )
        cphc_source = WarningSource(
            id='cphc_gis_central_pacific',
            name='NOAA Central Pacific Hurricane Center',
            backend='nhc_gis',
            country_code=None,
            url='https://example.test/cphc',
            kind='tropical_system',
            issuer_country_code='US',
            display_geography=DisplayGeography(
                kind='subunit',
                code='US-HI',
                name='Hawaii',
            ),
        )
        jma = TropicalSystem(
            id='jma-lala',
            source=jma_source.id,
            classification='Typhoon',
            name='LALA',
            headline='JMA LALA report',
            source_info=jma_source,
        )
        cphc = TropicalSystem(
            id='cphc-lala',
            source=cphc_source.id,
            classification='Hurricane',
            name='lala',
            headline='CPHC LALA report',
            source_info=cphc_source,
        )
        groups = [CanonicalTropicalSystem(name='LALA', observations=[jma, cphc])]

        with patch(
            'wevva_warnings.cli.get_canonical_tropical_systems',
            return_value=groups,
        ) as get_groups:
            result = runner.invoke(
                app,
                [
                    'tropical-groups',
                    '--source',
                    'jma_tropical',
                    '--source',
                    'cphc_gis_central_pacific',
                    '--debug',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        get_groups.assert_called_once_with(
            source_ids=['jma_tropical', 'cphc_gis_central_pacific'],
            debug=True,
        )
        self.assertIn('LALA', result.stderr)
        self.assertIn('Japan Meteorological Agency', result.stderr)
        self.assertIn('default (JP)', result.stderr)
        self.assertIn('NOAA Central Pacific Hurricane Center', result.stderr)
        self.assertIn('Hawaii (subunit: US-HI)', result.stderr)

    def test_tropical_near_command_passes_flags(self) -> None:
        system = TropicalSystem(
            id='al012026',
            source='nhc_gis_atlantic',
            classification='Hurricane',
            name='Alex',
            headline='Hurricane Alex Advisory #5',
        )

        with patch('wevva_warnings.cli.get_tropical_systems_near', return_value=[system]) as get_systems:
            result = runner.invoke(
                app,
                [
                    'tropical-near',
                    '25.0',
                    '-70.5',
                    '--radius-km',
                    '750',
                    '--source',
                    'nhc_gis_atlantic',
                    '--source',
                    'jma_tropical',
                    '--debug',
                    '--formatted',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        get_systems.assert_called_once_with(
            25.0,
            -70.5,
            radius_km=750.0,
            source_ids=['nhc_gis_atlantic', 'jma_tropical'],
            debug=True,
        )

    def test_tropical_near_command_prints_radius_error(self) -> None:
        result = runner.invoke(app, ['tropical-near', '25.0', '-70.5', '--radius-km', '-1'])

        self.assertEqual(result.exit_code, 2)
        self.assertIn('radius_km must be non-negative', result.output)

    def test_sources_command_prints_source_table(self) -> None:
        sample_sources = [
            WarningSource(
                id='alpha',
                name='Alpha Weather',
                backend='generic_cap',
                country_code='AA',
                url='https://example.com/alpha.xml',
                lang='en,fr',
                notes='Alpha notes.',
            )
        ]

        with patch('wevva_warnings.cli.list_sources', return_value=sample_sources):
            result = runner.invoke(app, ['sources'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Registered Sources (1)', result.stdout)
        self.assertIn('alpha', result.stdout)
        self.assertIn('alert', result.stdout)
        self.assertIn('generic_cap', result.stdout)

    def test_sources_command_passes_kind_filter(self) -> None:
        with patch('wevva_warnings.cli.list_sources', return_value=[]) as list_mock:
            result = runner.invoke(app, ['sources', '--kind', 'tropical-system'])

        self.assertEqual(result.exit_code, 0)
        list_mock.assert_called_once_with(kind='tropical_system')

    def test_sources_command_rejects_unknown_kind(self) -> None:
        result = runner.invoke(app, ['sources', '--kind', 'banana'])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("must be 'alert' or 'tropical_system'", result.output)
