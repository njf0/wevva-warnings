"""Tests for high-level source routing and point queries."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch
import warnings

from wevva_warnings import (
    WarningQueryProgress,
    deduplicate_alerts,
    get_alert_sources_for_country,
    get_alerts_for_country,
    get_native_alerts_for_point,
    get_reusable_alerts_for_country,
    get_tropical_systems,
    match_tropical_systems_to_point,
    match_alerts_to_point,
)
from wevva_warnings.models import Alert, TropicalSystem
from wevva_warnings.query import (
    get_alerts_for_point,
    get_alerts_for_source,
    get_tropical_systems_for_source,
    get_tropical_systems_near,
)
from wevva_warnings.registry import (
    LanguageNotSupportedError,
    UnsupportedCountryError,
    get_sources_for_country,
)
from wevva_warnings.sources import WarningSource

FMI_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>FMI Warnings</title>
    <item>
      <title>Wind warning</title>
      <link>https://alerts.fmi.fi/cap/alert/fmi-demo.xml</link>
    </item>
  </channel>
</rss>
"""

FMI_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>fmi-demo</identifier>
  <info>
    <language>fi-FI</language>
    <event>Tuulivaroitus</event>
    <headline>Suomenkielinen otsikko</headline>
    <severity>Moderate</severity>
    <description>Suomenkielinen kuvaus.</description>
    <area>
      <areaDesc>Suomi</areaDesc>
      <polygon>60.15,24.85 60.15,25.05 60.30,25.05 60.30,24.85 60.15,24.85</polygon>
    </area>
  </info>
  <info>
    <language>en-GB</language>
    <event>Wind warning</event>
    <headline>English headline</headline>
    <severity>Moderate</severity>
    <description>English description.</description>
    <area>
      <areaDesc>Finland</areaDesc>
      <polygon>60.15,24.85 60.15,25.05 60.30,25.05 60.30,24.85 60.15,24.85</polygon>
    </area>
  </info>
</alert>
"""

TC_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TCI CAP Feed EN</title>
    <language>en</language>
    <item>
      <title>Severe Thunderstorm Watch</title>
      <link>https://cap-sources.s3.amazonaws.com/tc-gov-en/2026-03-18-21-52-34.xml</link>
    </item>
  </channel>
</rss>
"""

TC_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>tc-demo-circle</identifier>
  <info>
    <language>en</language>
    <event>Thunderstorm Watch</event>
    <headline>Severe Thunderstorm Watch for TCI [March 19, 2026]</headline>
    <severity>Moderate</severity>
    <area>
      <areaDesc>Turks and Caicos Islands</areaDesc>
      <circle>21.5757,-71.7792 94</circle>
    </area>
  </info>
</alert>
"""

METSERVICE_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>MetService CAP</title>
    <item>
      <title>Future heavy rain warning</title>
      <link>https://alerts.metservice.com/cap/future.xml</link>
    </item>
  </channel>
</rss>
"""

METSERVICE_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>future-demo</identifier>
  <info>
    <language>en</language>
    <event>Heavy rain</event>
    <headline>Future heavy rain warning</headline>
    <severity>Moderate</severity>
    <effective>2026-03-13T10:00:00+00:00</effective>
    <expires>2026-03-13T18:00:00+00:00</expires>
    <description>Heavy rain is expected tomorrow.</description>
    <area>
      <areaDesc>New Zealand</areaDesc>
      <polygon>-41.50,172.00 -41.50,173.00 -41.00,173.00 -41.00,172.00 -41.50,172.00</polygon>
    </area>
  </info>
</alert>
"""


def fake_fetch_text(url: str, **_: object) -> str:
    """Return canned fixture content for a test URL.

    Parameters
    ----------
    url : str
        URL to fetch from the fixture map.

    Returns
    -------
    str
        XML content associated with the URL.

    """
    documents = {
        'https://alerts.fmi.fi/cap/feed/rss_en-GB.rss': FMI_FEED,
        'https://alerts.fmi.fi/cap/feed/rss_fi-FI.rss': FMI_FEED,
        'https://alerts.fmi.fi/cap/feed/rss_sv-FI.rss': FMI_FEED,
        'https://alerts.fmi.fi/cap/alert/fmi-demo.xml': FMI_CAP,
        'https://cap-sources.s3.amazonaws.com/tc-gov-en/rss.xml': TC_FEED,
        'https://cap-sources.s3.amazonaws.com/tc-gov-en/2026-03-18-21-52-34.xml': TC_CAP,
        'https://alerts.metservice.com/cap/rss': METSERVICE_FEED,
        'https://alerts.metservice.com/cap/future.xml': METSERVICE_CAP,
    }
    return documents[url]


class QueryTests(unittest.TestCase):
    def test_get_sources_for_country_defaults_to_english_source(self) -> None:
        sources = get_sources_for_country('FI')

        self.assertEqual([source.id for source in sources], ['fmi_en'])

    def test_get_sources_for_country_accepts_requested_language(self) -> None:
        sources = get_sources_for_country('FI', lang='fi-FI')

        self.assertEqual([source.id for source in sources], ['fmi_fi'])

    def test_get_sources_for_country_raises_for_unsupported_language(self) -> None:
        with self.assertRaises(LanguageNotSupportedError):
            get_sources_for_country('FI', lang='de')

    def test_get_alerts_for_point_warns_and_falls_back_for_unsupported_language(self) -> None:
        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter('always')
            alerts = get_alerts_for_point(60.22, 24.94, 'FI', lang='de')

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].source, 'fmi_en')
        self.assertIsNotNone(alerts[0].source_info)
        assert alerts[0].source_info is not None
        self.assertEqual(alerts[0].source_info.id, 'fmi_en')
        self.assertEqual(alerts[0].headline, 'English headline')
        self.assertEqual(len(caught), 1)

    def test_get_alert_sources_for_country_uses_point_query_language_fallback(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            sources = get_alert_sources_for_country('FI', lang='de')

        self.assertEqual([source.id for source in sources], ['fmi_en'])
        self.assertEqual(len(caught), 1)

    def test_country_candidates_can_be_matched_to_multiple_points_without_fetching_again(self) -> None:
        source = WarningSource(
            id='example',
            name='Example Weather Service',
            backend='example',
            country_code='EX',
            url='https://example.test/warnings',
            lang='en',
        )
        country_alerts = [
            Alert(
                id='berlin',
                source='example',
                event='Wind warning',
                headline='Berlin wind warning',
                geocodes={'EX-AREA': ['BERLIN']},
                parameters={'profile': ['country']},
                geometry={
                    'type': 'Polygon',
                    'coordinates': [[[13.2, 52.4], [13.6, 52.4], [13.6, 52.7], [13.2, 52.7], [13.2, 52.4]]],
                },
            ),
            Alert(
                id='munich',
                source='example',
                event='Rain warning',
                headline='Munich rain warning',
                geometry={
                    'type': 'Polygon',
                    'coordinates': [[[11.3, 48.0], [11.8, 48.0], [11.8, 48.3], [11.3, 48.3], [11.3, 48.0]]],
                },
            ),
            Alert(
                id='without-geometry',
                source='example',
                event='Fog warning',
                headline='Warning without geometry',
            ),
            Alert(
                id='berlin',
                source='example',
                event='Wind warning',
                headline='Repeated Berlin warning',
            ),
        ]

        class DummyBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source
                self.kwargs = kwargs
                return country_alerts

        backend = DummyBackend()
        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=backend),
        ):
            candidates = get_alerts_for_country('EX', lang='en')
            berlin = match_alerts_to_point(candidates, lat=52.52, lon=13.405)
            munich = match_alerts_to_point(candidates, lat=48.137, lon=11.575)

        self.assertEqual(backend.kwargs, {'lang': 'en', 'debug': False})
        self.assertEqual([alert.id for alert in candidates], ['berlin', 'munich', 'without-geometry'])
        self.assertIs(candidates[0].source_info, source)
        self.assertEqual(candidates[0].geocodes, {'EX-AREA': ['BERLIN']})
        self.assertEqual(candidates[0].parameters, {'profile': ['country']})
        self.assertEqual([alert.id for alert in berlin], ['berlin'])
        self.assertEqual([alert.id for alert in munich], ['munich'])

    def test_country_query_reports_country_specific_progress(self) -> None:
        source = WarningSource(
            id='example',
            name='Example Weather Service',
            backend='example',
            country_code='EX',
            url='https://example.test/warnings',
            lang='en',
        )

        class DummyBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return [Alert(id='one', source='example', event='Wind', headline='Wind warning')]

        events: list[tuple[str, dict[str, object]]] = []
        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
        ):
            alerts = get_alerts_for_country('EX', progress=lambda event, payload: events.append((event, payload)))

        self.assertEqual([alert.id for alert in alerts], ['one'])
        self.assertEqual(
            events,
            [
                ('country_query_started', {'country_code': 'EX'}),
                ('sources_total', {'total': 1}),
                ('source_started', {'source': 'example', 'provider_name': 'Example Weather Service'}),
                ('country_source_finished', {'source': 'example', 'candidates': 1, 'inactive_filtered': 0}),
                ('country_finished', {'alert_count': 1}),
            ],
        )

    def test_country_query_uses_native_backend_without_point_coordinates(self) -> None:
        source = WarningSource(
            id='native',
            name='Native Weather Service',
            backend='native',
            country_code='NX',
            url='https://example.test/alerts',
            lang='en',
        )
        native_alert = Alert(
            id='national-alert',
            source='native',
            event='Wind warning',
            headline='Native country candidate',
            geometry={
                'type': 'Polygon',
                'coordinates': [[[24.0, 60.0], [25.0, 60.0], [25.0, 61.0], [24.0, 61.0], [24.0, 60.0]]],
            },
        )

        class NativeBackend:
            uses_native_point_query = True

            def fetch_alerts(self, source, **kwargs):
                del source
                self.kwargs = kwargs
                return [native_alert]

        backend = NativeBackend()
        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=backend),
        ):
            candidates = get_alerts_for_country('NX')
            matches = match_alerts_to_point(candidates, lat=60.5, lon=24.5)

        self.assertEqual(backend.kwargs, {'lang': None, 'debug': False})
        self.assertEqual([alert.id for alert in matches], ['national-alert'])

    def test_split_candidate_queries_use_only_their_backend_capability(self) -> None:
        reusable_source = WarningSource(
            id='reusable',
            name='Reusable Weather Service',
            backend='reusable',
            country_code='MX',
            url='https://example.test/reusable',
            lang='en',
        )
        native_source = WarningSource(
            id='native',
            name='Native Weather Service',
            backend='native',
            country_code='MX',
            url='https://example.test/native',
            lang='en',
        )
        reusable_alert = Alert(
            id='reusable-alert',
            source='reusable',
            event='Rain warning',
            headline='Reusable rain warning',
            geometry={
                'type': 'Polygon',
                'coordinates': [[[24.0, 60.0], [25.0, 60.0], [25.0, 61.0], [24.0, 61.0], [24.0, 60.0]]],
            },
        )
        native_alert = Alert(
            id='native-alert',
            source='native',
            event='Wind warning',
            headline='Native wind warning',
        )

        class ReusableBackend:
            uses_native_point_query = False

            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def fetch_alerts(self, source, **kwargs):
                del source
                self.calls.append(kwargs)
                return [reusable_alert]

        class NativeBackend:
            uses_native_point_query = True

            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def fetch_alerts(self, source, **kwargs):
                del source
                self.calls.append(kwargs)
                return [native_alert]

        reusable_backend = ReusableBackend()
        native_backend = NativeBackend()

        def backend_for(source):
            return {'reusable': reusable_backend, 'native': native_backend}[source.id]

        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[reusable_source, native_source]),
            patch('wevva_warnings.query.get_backend', side_effect=backend_for),
        ):
            candidates = get_reusable_alerts_for_country('MX', lang='en')
            local_matches = match_alerts_to_point(candidates, lat=60.5, lon=24.5)
            native_matches = get_native_alerts_for_point(60.5, 24.5, 'MX', lang='en')
            combined = deduplicate_alerts([*local_matches, *native_matches])

        self.assertEqual([alert.id for alert in candidates], ['reusable-alert'])
        self.assertEqual(reusable_backend.calls, [{'lang': 'en', 'debug': False}])
        self.assertEqual(native_backend.calls, [{'lat': 60.5, 'lon': 24.5, 'lang': 'en', 'debug': False}])
        self.assertEqual([alert.id for alert in combined], ['reusable-alert', 'native-alert'])

    def test_split_candidate_queries_honour_active_only_and_filtered_progress(self) -> None:
        now = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)
        reusable_source = WarningSource('reusable', 'Reusable', 'reusable', 'MX', 'https://example.test/reusable', 'en')
        native_source = WarningSource('native', 'Native', 'native', 'MX', 'https://example.test/native', 'en')

        class ReusableBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return [
                    Alert(
                        id='future', source='reusable', event='Rain', headline='Future rain',
                        onset=datetime(2026, 3, 13, 12, 0, tzinfo=UTC),
                    ),
                ]

        class NativeBackend:
            uses_native_point_query = True

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return [
                    Alert(
                        id='current', source='native', event='Wind', headline='Current wind',
                        onset=datetime(2026, 3, 11, 12, 0, tzinfo=UTC),
                        expires=datetime(2026, 3, 13, 12, 0, tzinfo=UTC),
                    ),
                ]

        def backend_for(source):
            return {'reusable': ReusableBackend(), 'native': NativeBackend()}[source.id]

        reusable_events: list[tuple[str, dict[str, object]]] = []
        native_events: list[tuple[str, dict[str, object]]] = []
        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[reusable_source, native_source]),
            patch('wevva_warnings.query.get_backend', side_effect=backend_for),
            patch('wevva_warnings.query._utc_now', return_value=now),
        ):
            reusable = get_reusable_alerts_for_country(
                'MX', active_only=True, progress=lambda event, payload: reusable_events.append((event, payload))
            )
            native = get_native_alerts_for_point(
                60.5, 24.5, 'MX', active_only=True, progress=lambda event, payload: native_events.append((event, payload))
            )

        self.assertEqual(reusable, [])
        self.assertEqual([alert.id for alert in native], ['current'])
        self.assertEqual(reusable_events[1], ('sources_total', {'total': 1}))
        self.assertEqual(reusable_events[2][1]['source'], 'reusable')
        self.assertEqual(reusable_events[-1], ('country_finished', {'alert_count': 0}))
        self.assertEqual(native_events[1], ('sources_total', {'total': 1}))
        self.assertEqual(native_events[2][1]['source'], 'native')
        self.assertEqual(native_events[-1], ('finished', {'alert_count': 1}))

    def test_deduplicate_alerts_uses_point_query_rules(self) -> None:
        first = Alert(id='one', source='example', event='Wind', headline='Wind warning')
        repeated_id = Alert(id='one', source='example', event='Updated wind', headline='Updated warning')
        semantic_duplicate = Alert(id='two', source='example', event='Wind', headline='Wind warning')

        alerts = deduplicate_alerts([first, repeated_id, semantic_duplicate])

        self.assertEqual(alerts, [first])

    def test_country_and_local_matching_honour_active_only(self) -> None:
        now = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)
        source = WarningSource(
            id='example',
            name='Example Weather Service',
            backend='example',
            country_code='EX',
            url='https://example.test/warnings',
            lang='en',
        )
        future_alert = Alert(
            id='future',
            source='example',
            event='Rain warning',
            headline='Future rain warning',
            onset=datetime(2026, 3, 13, 12, 0, tzinfo=UTC),
            geometry={
                'type': 'Polygon',
                'coordinates': [[[24.0, 60.0], [25.0, 60.0], [25.0, 61.0], [24.0, 61.0], [24.0, 60.0]]],
            },
        )

        class DummyBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return [future_alert]

        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
            patch('wevva_warnings.query._utc_now', return_value=now),
        ):
            candidates = get_alerts_for_country('EX')
            self.assertEqual(match_alerts_to_point(candidates, lat=60.5, lon=24.5, active_only=True), [])
            self.assertEqual(get_alerts_for_country('EX', active_only=True), [])

    def test_get_alerts_for_point_filters_by_polygon_geometry(self) -> None:
        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            matching = get_alerts_for_point(60.22, 24.94, 'FI')
            missing = get_alerts_for_point(61.00, 26.00, 'FI')

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].headline, 'English headline')
        self.assertEqual(missing, [])

    def test_get_alerts_for_point_supports_circle_geometry(self) -> None:
        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = get_alerts_for_point(21.5757, -71.7792, 'TC')

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].source, 'tci_en')
        self.assertIsNotNone(alerts[0].source_info)
        assert alerts[0].source_info is not None
        self.assertEqual(alerts[0].source_info.id, 'tci_en')
        self.assertEqual(alerts[0].headline, 'Severe Thunderstorm Watch for TCI [March 19, 2026]')

    def test_get_alerts_for_point_dedupes_semantically_identical_alerts(self) -> None:
        duplicate_alerts = [
            Alert(
                id='dup-1',
                source='meteoalarm_atom_estonia',
                event='Ground frost warning',
                headline='Ground frost warning',
                severity='Moderate',
                description='Ground frost, decrease soil surface temperature to 0..-3°C.',
                onset=datetime.fromisoformat('2026-04-20T21:00:00+03:00'),
                expires=datetime.fromisoformat('2026-04-21T09:00:00+03:00'),
                geometry={
                    'type': 'Polygon',
                    'coordinates': [[[24.0, 58.0], [25.0, 58.0], [25.0, 59.0], [24.0, 59.0], [24.0, 58.0]]],
                },
            ),
            Alert(
                id='dup-2',
                source='meteoalarm_atom_estonia',
                event='Ground frost warning',
                headline='Ground frost warning',
                severity='Moderate',
                description='Ground frost, decrease soil surface temperature to 0..-3°C.',
                onset=datetime.fromisoformat('2026-04-20T21:00:00+03:00'),
                expires=datetime.fromisoformat('2026-04-21T09:00:00+03:00'),
                geometry={
                    'type': 'Polygon',
                    'coordinates': [[[24.0, 58.0], [25.0, 58.0], [25.0, 59.0], [24.0, 59.0], [24.0, 58.0]]],
                },
            ),
        ]

        class DummyBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return duplicate_alerts

        dummy_source = type('SourceLike', (), {'id': 'meteoalarm_atom_estonia'})()

        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[dummy_source]),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
        ):
            alerts = get_alerts_for_point(58.5, 24.5, 'EE')

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].headline, 'Ground frost warning')

    def test_get_alerts_for_point_without_progress_preserves_query_behaviour(self) -> None:
        source = WarningSource(
            id='example',
            name='Example Weather Service',
            backend='example',
            country_code='EX',
            url='https://example.test/warnings',
            lang='en',
        )
        alert = Alert(
            id='matching',
            source='example',
            event='Wind warning',
            headline='Matching warning',
            geometry={
                'type': 'Polygon',
                'coordinates': [[[24.0, 60.0], [25.0, 60.0], [25.0, 61.0], [24.0, 61.0], [24.0, 60.0]]],
            },
        )

        class DummyBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source
                self.kwargs = kwargs
                return [alert]

        backend = DummyBackend()
        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=backend),
        ):
            alerts = get_alerts_for_point(60.5, 24.5, 'EX', lang='en', active_only=True)

        self.assertEqual([returned.id for returned in alerts], ['matching'])
        self.assertEqual(
            backend.kwargs,
            {'lat': 60.5, 'lon': 24.5, 'lang': 'en', 'debug': False},
        )

    def test_get_alerts_for_point_reports_public_progress(self) -> None:
        source = WarningSource(
            id='example',
            name='Example Weather Service',
            backend='example',
            country_code='EX',
            url='https://example.test/warnings',
            lang='en',
        )
        source_alerts = [
            Alert(
                id='matching',
                source='example',
                event='Wind warning',
                headline='Matching warning',
                geometry={
                    'type': 'Polygon',
                    'coordinates': [[[24.0, 60.0], [25.0, 60.0], [25.0, 61.0], [24.0, 61.0], [24.0, 60.0]]],
                },
            ),
            Alert(
                id='missing-geometry',
                source='example',
                event='Rain warning',
                headline='Warning without geometry',
            ),
        ]

        class DummyBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return source_alerts

        events: list[tuple[str, dict[str, object]]] = []

        def record_progress(event: str, payload: dict[str, object]) -> None:
            events.append((event, payload))

        progress: WarningQueryProgress = record_progress
        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
        ):
            alerts = get_alerts_for_point(60.5, 24.5, 'EX', progress=progress)

        self.assertEqual([alert.id for alert in alerts], ['matching'])
        self.assertEqual(
            [event for event, _ in events],
            [
                'query_started',
                'sources_total',
                'source_started',
                'alerts_total',
                'alerts_checked',
                'alerts_checked',
                'source_finished',
                'finished',
            ],
        )
        self.assertEqual(events[2][1], {'source': 'example', 'provider_name': 'Example Weather Service'})
        self.assertEqual(
            events[5][1],
            {'source': 'example', 'completed': 2, 'total': 2, 'matched': 1, 'phase': 'matching'},
        )
        self.assertEqual(
            events[6][1],
            {
                'source': 'example',
                'candidates': 2,
                'matched': 1,
                'skipped_without_geometry': 1,
                'inactive_filtered': 0,
            },
        )
        self.assertEqual(events[-1], ('finished', {'alert_count': 1}))

    def test_get_alerts_for_point_reports_cap_document_progress_without_debug(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = get_alerts_for_point(
                60.22,
                24.94,
                'FI',
                progress=lambda event, payload: events.append((event, payload)),
            )

        self.assertEqual(len(alerts), 1)
        self.assertIn(
            ('alerts_total', {'source': 'fmi_en', 'total': 1, 'phase': 'documents'}),
            events,
        )
        self.assertIn(
            (
                'alerts_checked',
                {'source': 'fmi_en', 'completed': 1, 'total': 1, 'phase': 'documents'},
            ),
            events,
        )

    def test_native_point_query_reports_no_document_stage(self) -> None:
        source = WarningSource(
            id='native',
            name='Native Weather Service',
            backend='native',
            country_code='NX',
            url='https://example.test/point',
            lang='en',
        )
        native_alert = Alert(
            id='native-match',
            source='native',
            event='Wind warning',
            headline='Native point result',
        )

        class NativeBackend:
            uses_native_point_query = True

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return [native_alert]

        events: list[tuple[str, dict[str, object]]] = []
        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=NativeBackend()),
        ):
            alerts = get_alerts_for_point(
                60.5,
                24.5,
                'NX',
                progress=lambda event, payload: events.append((event, payload)),
            )

        self.assertEqual([alert.id for alert in alerts], ['native-match'])
        phases = [payload.get('phase') for event, payload in events if event == 'alerts_total']
        self.assertEqual(phases, ['matching'])
        self.assertEqual(
            events[-2],
            (
                'source_finished',
                {
                    'source': 'native',
                    'candidates': 1,
                    'matched': 1,
                    'skipped_without_geometry': 0,
                    'inactive_filtered': 0,
                },
            ),
        )
    def test_progress_callback_failure_does_not_interrupt_point_query(self) -> None:
        source = WarningSource(
            id='example',
            name='Example Weather Service',
            backend='example',
            country_code='EX',
            url='https://example.test/warnings',
            lang='en',
        )
        alert = Alert(
            id='matching',
            source='example',
            event='Wind warning',
            headline='Matching warning',
            geometry={
                'type': 'Polygon',
                'coordinates': [[[24.0, 60.0], [25.0, 60.0], [25.0, 61.0], [24.0, 61.0], [24.0, 60.0]]],
            },
        )

        class DummyBackend:
            uses_native_point_query = False

            def fetch_alerts(self, source, **kwargs):
                del source, kwargs
                return [alert]

        def broken_progress(event: str, payload: dict[str, object]) -> None:
            del event, payload
            raise RuntimeError('UI closed')

        with (
            patch('wevva_warnings.query.get_sources_for_country', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
        ):
            alerts = get_alerts_for_point(60.5, 24.5, 'EX', progress=broken_progress)

        self.assertEqual([returned.id for returned in alerts], ['matching'])

    def test_get_alerts_for_source_active_only_filters_future_alerts(self) -> None:
        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.query._utc_now', return_value=datetime(2026, 3, 12, 22, 0, tzinfo=UTC)),
        ):
            alerts = get_alerts_for_source('metservice_nz', active_only=True)

        self.assertEqual(alerts, [])

    def test_get_alerts_for_point_raises_for_unknown_country(self) -> None:
        with self.assertRaises(UnsupportedCountryError):
            get_alerts_for_point(0.0, 0.0, 'ZZ')

    def test_get_alerts_for_source_returns_empty_for_unknown_source(self) -> None:
        self.assertEqual(get_alerts_for_source('missing'), [])

    def test_get_tropical_systems_for_source_returns_tropical_systems(self) -> None:
        system = TropicalSystem(
            id='al012026',
            source='nhc_gis_atlantic',
            classification='Tropical Storm',
            name='ALPHA',
            headline='...ALPHA MOVING NORTHWEST...',
        )

        class DummyBackend:
            def fetch_tropical_systems(self, source, *, debug=False):
                del source, debug
                return [system]

        source = WarningSource(
            id='nhc_gis_atlantic',
            name='NHC',
            backend='nhc_gis',
            country_code=None,
            url='https://www.nhc.noaa.gov/gis-at.xml',
            lang='en',
            kind='tropical_system',
        )

        with (
            patch('wevva_warnings.query.get_source', return_value=source),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
        ):
            systems = get_tropical_systems_for_source('nhc_gis_atlantic', debug=True)

        self.assertEqual(systems, [system])
        self.assertIs(systems[0].source_info, source)

    def test_get_tropical_systems_for_source_ignores_alert_sources(self) -> None:
        source = WarningSource(
            id='nws',
            name='NWS',
            backend='nws',
            country_code='US',
            url='https://api.weather.gov/alerts/active',
            lang='en',
        )

        with patch('wevva_warnings.query.get_source', return_value=source):
            systems = get_tropical_systems_for_source('nws')

        self.assertEqual(systems, [])

    def test_get_tropical_systems_fetches_raw_selected_or_all_sources_without_a_point(self) -> None:
        first_source = WarningSource(
            id='first',
            name='First Tropical Centre',
            backend='first',
            country_code=None,
            url='https://example.test/first',
            lang='en',
            kind='tropical_system',
        )
        second_source = WarningSource(
            id='second',
            name='Second Tropical Centre',
            backend='second',
            country_code=None,
            url='https://example.test/second',
            lang='en',
            kind='tropical_system',
        )
        systems_by_source = {
            'first': [
                TropicalSystem(
                    id='first-current',
                    source='first',
                    classification='Tropical Storm',
                    name='ALPHA',
                    headline='First current report',
                )
            ],
            'second': [
                TropicalSystem(
                    id='second-current',
                    source='second',
                    classification='Typhoon',
                    name='BETA',
                    headline='Second current report',
                )
            ],
        }

        class DummyBackend:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []

            def fetch_tropical_systems(self, source, **kwargs):
                self.calls.append((source.id, kwargs))
                return systems_by_source[source.id]

        backend = DummyBackend()
        sources = {'first': first_source, 'second': second_source}
        with (
            patch('wevva_warnings.query.get_source', side_effect=sources.get),
            patch('wevva_warnings.query.get_backend', return_value=backend),
        ):
            systems = get_tropical_systems(source_ids=['second', 'missing', 'second', 'first'])

        self.assertEqual([system.id for system in systems], ['second-current', 'first-current'])
        self.assertEqual(
            backend.calls,
            [
                ('second', {'debug': False}),
                ('first', {'debug': False}),
            ],
        )
        self.assertIs(systems[0].source_info, second_source)
        self.assertIs(systems[1].source_info, first_source)

        backend.calls.clear()
        with (
            patch('wevva_warnings.query.list_tropical_sources', return_value=[first_source, second_source]),
            patch('wevva_warnings.query.get_backend', return_value=backend),
        ):
            all_systems = get_tropical_systems()

        self.assertEqual([system.id for system in all_systems], ['first-current', 'second-current'])
        self.assertEqual(
            backend.calls,
            [
                ('first', {'debug': False}),
                ('second', {'debug': False}),
            ],
        )

    def test_match_tropical_systems_to_point_is_local_and_uses_proximity_rules(self) -> None:
        systems = [
            TropicalSystem(
                id='near-center',
                source='first',
                classification='Tropical Storm',
                name='ALPHA',
                headline='Near centre',
                center_lat=25.0,
                center_lon=-70.0,
            ),
            TropicalSystem(
                id='inside-polygon',
                source='second',
                classification='Typhoon',
                name='BETA',
                headline='Inside polygon',
                geometries={
                    'watch_warning': {
                        'type': 'Polygon',
                        'coordinates': [[[-71.0, 24.0], [-69.0, 24.0], [-69.0, 26.0], [-71.0, 26.0], [-71.0, 24.0]]],
                    }
                },
            ),
            TropicalSystem(
                id='far',
                source='first',
                classification='Tropical Depression',
                name='GAMMA',
                headline='Far away',
                center_lat=40.0,
                center_lon=-90.0,
            ),
            TropicalSystem(
                id='near-center',
                source='first',
                classification='Tropical Storm',
                name='ALPHA',
                headline='Duplicate current report',
                center_lat=25.0,
                center_lon=-70.0,
            ),
        ]

        matches = match_tropical_systems_to_point(systems, lat=25.0, lon=-70.5, radius_km=100)

        self.assertEqual([system.id for system in matches], ['near-center', 'inside-polygon'])
        with self.assertRaisesRegex(ValueError, 'radius_km must be non-negative'):
            match_tropical_systems_to_point(systems, lat=25.0, lon=-70.5, radius_km=-1)

    def test_get_tropical_systems_near_matches_centers_and_polygonal_geometries(self) -> None:
        systems = [
            TropicalSystem(
                id='near-center',
                source='nhc_gis_atlantic',
                classification='Tropical Storm',
                name='ALPHA',
                headline='Near center',
                center_lat=25.0,
                center_lon=-70.0,
            ),
            TropicalSystem(
                id='inside-cone',
                source='nhc_gis_atlantic',
                classification='Tropical Storm',
                name='BETA',
                headline='Inside cone',
                geometries={
                    'cone': {
                        'type': 'Polygon',
                        'coordinates': [[[-71.0, 24.0], [-69.0, 24.0], [-69.0, 26.0], [-71.0, 26.0], [-71.0, 24.0]]],
                    }
                },
            ),
            TropicalSystem(
                id='too-far',
                source='nhc_gis_atlantic',
                classification='Tropical Storm',
                name='GAMMA',
                headline='Too far',
                center_lat=40.0,
                center_lon=-90.0,
            ),
        ]

        class DummyBackend:
            def fetch_tropical_systems(self, source, **kwargs):
                del source, kwargs
                return systems

        source = WarningSource(
            id='nhc_gis_atlantic',
            name='NHC',
            backend='nhc_gis',
            country_code=None,
            url='https://www.nhc.noaa.gov/gis-at.xml',
            lang='en',
            kind='tropical_system',
        )

        with (
            patch('wevva_warnings.query.list_tropical_sources', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
        ):
            matches = get_tropical_systems_near(25.0, -70.5, radius_km=100)

        self.assertEqual([system.id for system in matches], ['near-center', 'inside-cone'])
        self.assertIs(matches[0].source_info, source)
        self.assertIs(matches[1].source_info, source)

    def test_get_tropical_systems_near_reports_fetch_then_check_progress(self) -> None:
        first_source = WarningSource(
            id='first',
            name='First Tropical Centre',
            backend='first',
            country_code=None,
            url='https://example.test/first',
            lang='en',
            kind='tropical_system',
        )
        second_source = WarningSource(
            id='second',
            name='Second Tropical Centre',
            backend='second',
            country_code=None,
            url='https://example.test/second',
            lang='en',
            kind='tropical_system',
        )
        systems_by_source = {
            'first': [
                TropicalSystem(
                    id='near',
                    source='first',
                    classification='Tropical Storm',
                    name='ALPHA',
                    headline='Near centre',
                    center_lat=25.0,
                    center_lon=-70.0,
                ),
                TropicalSystem(
                    id='far',
                    source='first',
                    classification='Tropical Storm',
                    name='BETA',
                    headline='Far away',
                    center_lat=40.0,
                    center_lon=-90.0,
                ),
                TropicalSystem(
                    id='near',
                    source='first',
                    classification='Tropical Storm',
                    name='ALPHA',
                    headline='Repeated near centre',
                    center_lat=25.0,
                    center_lon=-70.0,
                ),
            ],
            'second': [
                TropicalSystem(
                    id='inside',
                    source='second',
                    classification='Tropical Storm',
                    name='GAMMA',
                    headline='Inside cone',
                    geometries={
                        'cone': {
                            'type': 'Polygon',
                            'coordinates': [[[-71.0, 24.0], [-69.0, 24.0], [-69.0, 26.0], [-71.0, 26.0], [-71.0, 24.0]]],
                        }
                    },
                )
            ],
        }

        class DummyBackend:
            def fetch_tropical_systems(self, source, **kwargs):
                from wevva_warnings._debug import emit_progress

                self.calls.append((source.id, kwargs))
                emit_progress('alerts_total', source=source.id, total=99, phase='documents')
                return systems_by_source[source.id]

            def __init__(self):
                self.calls: list[tuple[str, dict[str, object]]] = []

        backend = DummyBackend()
        events: list[tuple[str, dict[str, object]]] = []

        with (
            patch('wevva_warnings.query.list_tropical_sources', return_value=[first_source, second_source]),
            patch('wevva_warnings.query.get_backend', return_value=backend),
        ):
            matches = get_tropical_systems_near(
                25.0,
                -70.5,
                radius_km=100,
                progress=lambda event, payload: events.append((event, payload)),
            )

        self.assertEqual([system.id for system in matches], ['near', 'inside'])
        self.assertEqual(
            backend.calls,
            [
                ('first', {'debug': False}),
                ('second', {'debug': False}),
            ],
        )
        self.assertEqual(
            events,
            [
                ('tropical_fetch_started', {'lat': 25.0, 'lon': -70.5, 'source_total': 2}),
                ('tropical_source_started', {'source': 'first', 'provider_name': 'First Tropical Centre'}),
                ('tropical_source_finished', {'source': 'first', 'candidates': 3}),
                ('tropical_source_started', {'source': 'second', 'provider_name': 'Second Tropical Centre'}),
                ('tropical_source_finished', {'source': 'second', 'candidates': 1}),
                ('tropical_check_total', {'total': 4}),
                ('tropical_checked', {'completed': 1, 'total': 4, 'matched': 1}),
                ('tropical_checked', {'completed': 2, 'total': 4, 'matched': 1}),
                ('tropical_checked', {'completed': 3, 'total': 4, 'matched': 2}),
                ('tropical_checked', {'completed': 4, 'total': 4, 'matched': 3}),
                ('tropical_finished', {'system_count': 2}),
            ],
        )

    def test_get_tropical_systems_near_progress_filters_sources_and_reports_zero_candidates(self) -> None:
        available_source = WarningSource(
            id='available',
            name='Available Tropical Centre',
            backend='available',
            country_code=None,
            url='https://example.test/available',
            lang='en',
            kind='tropical_system',
        )
        unavailable_source = WarningSource(
            id='unavailable',
            name='Unavailable Tropical Centre',
            backend='unavailable',
            country_code=None,
            url='https://example.test/unavailable',
            lang='en',
            kind='tropical_system',
        )

        class EmptyBackend:
            def fetch_tropical_systems(self, source, **kwargs):
                del source, kwargs
                return []

        sources = {'available': available_source, 'unavailable': unavailable_source}
        events: list[tuple[str, dict[str, object]]] = []
        with (
            patch('wevva_warnings.query.get_source', side_effect=sources.get),
            patch(
                'wevva_warnings.query.get_backend',
                side_effect=lambda source: EmptyBackend() if source.id == 'available' else None,
            ),
        ):
            matches = get_tropical_systems_near(
                25.0,
                -70.0,
                source_ids=['available', 'unavailable', 'available', 'missing'],
                progress=lambda event, payload: events.append((event, payload)),
            )

        self.assertEqual(matches, [])
        self.assertEqual(
            events,
            [
                ('tropical_fetch_started', {'lat': 25.0, 'lon': -70.0, 'source_total': 1}),
                ('tropical_source_started', {'source': 'available', 'provider_name': 'Available Tropical Centre'}),
                ('tropical_source_finished', {'source': 'available', 'candidates': 0}),
                ('tropical_check_total', {'total': 0}),
                ('tropical_finished', {'system_count': 0}),
            ],
        )

    def test_tropical_progress_callback_failure_does_not_interrupt_proximity_query(self) -> None:
        system = TropicalSystem(
            id='near',
            source='example',
            classification='Tropical Storm',
            name='ALPHA',
            headline='Near centre',
            center_lat=25.0,
            center_lon=-70.0,
        )
        source = WarningSource(
            id='example',
            name='Example Tropical Centre',
            backend='example',
            country_code=None,
            url='https://example.test/tropical',
            lang='en',
            kind='tropical_system',
        )

        class DummyBackend:
            def fetch_tropical_systems(self, source, **kwargs):
                del source, kwargs
                return [system]

        def broken_progress(event: str, payload: dict[str, object]) -> None:
            del event, payload
            raise RuntimeError('UI closed')

        with (
            patch('wevva_warnings.query.list_tropical_sources', return_value=[source]),
            patch('wevva_warnings.query.get_backend', return_value=DummyBackend()),
        ):
            matches = get_tropical_systems_near(25.0, -70.5, radius_km=100, progress=broken_progress)

        self.assertEqual([system.id for system in matches], ['near'])

    def test_get_tropical_systems_near_rejects_negative_radius(self) -> None:
        with self.assertRaises(ValueError):
            get_tropical_systems_near(25.0, -70.0, radius_km=-1)
