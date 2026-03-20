"""Tests for the command-line interface."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from wevva_warnings.cli import app
from wevva_warnings.models import Alert
from wevva_warnings.registry import UnsupportedCountryError
from wevva_warnings.sources import WarningSource

runner = CliRunner()


class CLITests(unittest.TestCase):
    def test_point_command_passes_flags(self) -> None:
        with patch('wevva_warnings.cli.get_alerts_for_point', return_value=[]) as get_alerts:
            result = runner.invoke(app, ['point', '40.71', '-74.00', 'DE', '--lang', 'de', '--debug', '--active-only'])

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

    def test_source_command_passes_flags(self) -> None:
        source = WarningSource(
            id='fmi_cap_en',
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
            result = runner.invoke(app, ['source', 'fmi_cap_en', '--debug', '--active-only'])

        self.assertEqual(result.exit_code, 0)
        get_alerts.assert_called_once_with('fmi_cap_en', debug=True, active_only=True)

    def test_source_command_prints_human_output(self) -> None:
        alert = Alert(
            id='demo',
            source='fmi_cap_en',
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
                    id='fmi_cap_en',
                    name='FMI',
                    backend='generic_cap',
                    country_code='FI',
                    url='https://alerts.fmi.fi/cap/feed/rss_en-GB.rss',
                    lang='en',
                ),
            ),
            patch('wevva_warnings.cli.get_alerts_for_source', return_value=[alert]),
        ):
            result = runner.invoke(app, ['source', 'fmi_cap_en'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Wind Warning', result.stdout)
        self.assertIn('Moderate', result.stdout)
        self.assertIn('Strong west winds expected.', result.stdout)

    def test_source_command_prints_unknown_source_error(self) -> None:
        with patch('wevva_warnings.cli.get_source', return_value=None):
            result = runner.invoke(app, ['source', 'missing'])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("source is registered with id 'missing'", result.output)

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
        self.assertIn('generic_cap', result.stdout)
