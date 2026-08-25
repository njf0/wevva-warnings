"""Focused tests for lazy tropical supplementary products."""

from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from wevva_warnings import (
    TropicalProduct,
    TropicalSystem,
    get_tropical_products,
    get_tropical_systems_for_source,
    group_tropical_systems,
)
from wevva_warnings.backends.base import BackendError
from wevva_warnings.backends._tropical_text import plain_text_to_markdown
from wevva_warnings.backends.nhc_gis import (
    NHCGISBackend,
    _nhc_product_markdown,
    _normalize_nhc_product_content,
)
from wevva_warnings.registry import get_backend, get_source


def _system(*, source: str = 'nhc_gis_eastern_pacific', wallet: str = 'EP3') -> TropicalSystem:
    return TropicalSystem(
        id='ep082026',
        source=source,
        classification='Tropical Depression',
        name='HERNAN',
        headline='Hernan advisory',
        basin='Eastern Pacific',
        parameters={'NHC Wallet': [wallet], 'ATCF ID': ['ep082026']},
    )


def _feed(
    *,
    title: str,
    product_code: str,
    wallet: str = 'EP3',
    system_id: str = 'EP082026',
    prose: str = 'Official prose &amp; detail.',
) -> str:
    if product_code == 'TCP':
        body = f'BULLETIN<br />{title}<br />NWS National Hurricane Center {system_id}<br /><br />{prose}'
    elif product_code == 'TCD':
        body = f'{title}<br />NWS National Hurricane Center {system_id}<br /><br />{prose}'
    else:
        body = f'BULLETIN<br />{system_id}<br />{prose}'
    return f"""\
<rss><channel><item>
  <title>{title}</title>
  <description><![CDATA[820 <br />WTPZ33 KNHC 141437<br />{product_code}{wallet}<br /><br />{body}]]></description>
  <pubDate>Fri, 14 Aug 2026 20:34:27 +0000</pubDate>
  <link>https://www.nhc.noaa.gov/text/{product_code}{wallet}.shtml</link>
</item></channel></rss>
"""


class TropicalProductModelTests(unittest.TestCase):
    def test_small_product_model_preserves_provider_vocabulary_and_optional_fields(self) -> None:
        product = TropicalProduct(
            kind='analysis',
            label='Technical Bulletin',
            content='Official analysis.',
        )

        self.assertEqual(product.kind, 'analysis')
        self.assertEqual(product.label, 'Technical Bulletin')
        self.assertEqual(product.content_format, 'markdown')
        self.assertIsNone(product.title)
        self.assertIsNone(product.issued_at)
        self.assertIsNone(product.url)
        self.assertIsNone(product.data)

    def test_product_content_drops_leading_blank_lines_but_keeps_markdown_indentation(self) -> None:
        heading = TropicalProduct(
            kind='advisory',
            label='Public Advisory',
            content='\n \t\r\n# Official advisory\nBody',
        )
        fixed_width = TropicalProduct(
            kind='warnings',
            label='Warnings',
            content='\n\n    FIXED-WIDTH CONTENT',
        )

        self.assertEqual(heading.content, '# Official advisory\nBody')
        self.assertEqual(fixed_width.content, '    FIXED-WIDTH CONTENT')

    def test_plain_text_markdown_keeps_first_meaningful_line_indentation(self) -> None:
        product = TropicalProduct(
            kind='advisory',
            label='Bulletin',
            content=plain_text_to_markdown('\n\n    PROVIDER TABLE\nBody'),
        )

        self.assertEqual(product.content, '    PROVIDER TABLE  \nBody')


class TropicalProductQueryTests(unittest.TestCase):
    def test_normal_discovery_does_not_fetch_products_but_product_query_does(self) -> None:
        source = get_source('nhc_gis_eastern_pacific')
        assert source is not None
        backend = get_backend(source)
        assert backend is not None
        system = _system()
        product = TropicalProduct(kind='advisory', label='Public Advisory')

        with (
            patch.object(backend, 'fetch_tropical_systems', return_value=[system]) as fetch_systems,
            patch.object(backend, 'fetch_tropical_products', return_value=[product]) as fetch_products,
        ):
            systems = get_tropical_systems_for_source(source.id)
            fetch_products.assert_not_called()
            products = get_tropical_products(systems[0])

        fetch_systems.assert_called_once_with(source, debug=False)
        fetch_products.assert_called_once_with(source, systems[0], debug=False)
        self.assertEqual(products, [product])

    def test_backend_without_supplementary_support_returns_an_empty_list(self) -> None:
        system = TropicalSystem(
            id='AU2026_TEST',
            source='bom_tropical',
            classification='Tropical Cyclone',
            name='TEST',
            headline='Tropical Cyclone TEST',
        )
        self.assertEqual(get_tropical_products(system), [])

    def test_wallet_is_routing_metadata_not_canonical_identity(self) -> None:
        first = _system(wallet='EP3')
        second = TropicalSystem(
            id='jma-event-8',
            source='jma_tropical',
            classification='Typhoon',
            name=' hernan ',
            headline='Typhoon HERNAN',
        )

        groups = group_tropical_systems([first, second])

        self.assertEqual(len(groups), 1)
        self.assertEqual([observation.id for observation in groups[0].observations], ['ep082026', 'jma-event-8'])


class NHCProductTests(unittest.TestCase):
    def test_wallet_products_are_semantic_ordered_and_stale_products_are_omitted(self) -> None:
        system = _system()
        documents = {
            'https://www.nhc.noaa.gov/xml/TCPEP3.xml': _feed(
                title='Tropical Depression Hernan Advisory Number 8',
                product_code='TCP',
            ),
            'https://www.nhc.noaa.gov/xml/TCDEP3.xml': _feed(
                title='Tropical Depression Hernan Discussion Number 8',
                product_code='TCD',
            ),
            'https://www.nhc.noaa.gov/xml/PWSEP3.xml': _feed(
                title='Tropical Depression Hernan Wind Speed Probabilities Number 8',
                product_code='PWS',
                prose='<pre>Probability table</pre>',
            ),
            'https://www.nhc.noaa.gov/xml/TCVEP3.xml': _feed(
                title='Old storm breakpoints',
                product_code='TCV',
                system_id='EP032026',
            ),
        }

        def fake_fetch_text(url: str, **_: object) -> str:
            if url.endswith('TCUEP3.xml'):
                raise BackendError('optional update unavailable')
            return documents[url]

        with patch('wevva_warnings.backends.nhc_gis.fetch_text', side_effect=fake_fetch_text):
            products = NHCGISBackend().fetch_tropical_products(
                get_source('nhc_gis_eastern_pacific'),  # type: ignore[arg-type]
                system,
            )

        self.assertEqual(
            [(product.kind, product.label) for product in products],
            [
                ('advisory', 'Public Advisory'),
                ('analysis', 'Forecast Discussion'),
                ('probabilities', 'Wind Probabilities'),
            ],
        )
        self.assertEqual(products[0].issued_at, datetime(2026, 8, 14, 20, 34, 27, tzinfo=UTC))
        self.assertEqual(
            [product.content_format for product in products],
            ['markdown', 'markdown', 'plain'],
        )
        self.assertNotIn('<br', products[0].content or '')
        self.assertIn('# Tropical Depression Hernan Advisory Number 8', products[0].content or '')
        self.assertIn('Official prose & detail.', products[0].content or '')
        self.assertEqual(products[0].data, {'product_code': 'TCP'})

    def test_wind_probabilities_and_update_remain_plain_text(self) -> None:
        system = _system()

        def fake_fetch_text(url: str, **_: object) -> str:
            if url.endswith('PWSEP3.xml'):
                return _feed(
                    title='Tropical Depression Hernan Wind Speed Probabilities Number 8',
                    product_code='PWS',
                    prose='<pre>34-knot probabilities by location</pre>',
                )
            if url.endswith('TCUEP3.xml'):
                return _feed(
                    title='Tropical Depression Hernan Tropical Cyclone Update',
                    product_code='TCU',
                    prose='This is an official update.',
                )
            return '<rss/>'

        with patch('wevva_warnings.backends.nhc_gis.fetch_text', side_effect=fake_fetch_text):
            products = NHCGISBackend().fetch_tropical_products(
                get_source('nhc_gis_eastern_pacific'),  # type: ignore[arg-type]
                system,
            )

        self.assertEqual(
            [(product.label, product.content_format) for product in products],
            [('Wind Probabilities', 'plain'), ('Update', 'plain')],
        )
        self.assertIn('34-knot probabilities by location', products[0].content or '')
        self.assertFalse((products[0].content or '').startswith('    '))
        self.assertIn('This is an official update.', products[1].content or '')

    def test_at_ep_and_cp_wallets_resolve_their_documented_product_urls(self) -> None:
        source_wallets = (
            ('nhc_gis_atlantic', 'AT1'),
            ('nhc_gis_eastern_pacific', 'EP3'),
            ('cphc_gis_central_pacific', 'CP2'),
        )
        for source_id, wallet in source_wallets:
            system = _system(source=source_id, wallet=wallet)
            with self.subTest(wallet=wallet), patch(
                'wevva_warnings.backends.nhc_gis.fetch_text',
                return_value='<rss/>',
            ) as fetch_text:
                NHCGISBackend().fetch_tropical_products(
                    get_source(source_id),  # type: ignore[arg-type]
                    system,
                )
            self.assertEqual(
                [call.args[0] for call in fetch_text.call_args_list],
                [
                    f'https://www.nhc.noaa.gov/xml/TCP{wallet}.xml',
                    f'https://www.nhc.noaa.gov/xml/TCD{wallet}.xml',
                    f'https://www.nhc.noaa.gov/xml/PWS{wallet}.xml',
                    f'https://www.nhc.noaa.gov/xml/TCV{wallet}.xml',
                    f'https://www.nhc.noaa.gov/xml/TCU{wallet}.xml',
                ],
            )

    def test_transport_cleanup_is_conservative_and_prose_is_not_rewritten(self) -> None:
        system = _system()
        normalized = _normalize_nhc_product_content(
            '820<br>WTPZ33 KNHC 141437<br>TCPEP3<br><br>Line one.<br />Line two &amp; three.',
            product_code='TCP',
            system=system,
        )
        unrecognized = _normalize_nhc_product_content(
            'NOT A WMO HEADER<br />Line one.',
            product_code='TCP',
            system=system,
        )

        self.assertEqual(normalized, 'Line one.\nLine two & three.')
        self.assertEqual(unrecognized, 'NOT A WMO HEADER\nLine one.')

    def test_public_advisory_markdown_formats_known_sections_and_fixed_summary(self) -> None:
        content = """\
BULLETIN
Tropical Storm Alpha Advisory Number 1
NWS National Hurricane Center Miami FL AL012026
1100 AM AST Fri Aug 14 2026

...ALPHA CONTINUES NORTHWEST...

SUMMARY OF 1100 AM AST...1500 UTC...INFORMATION
------------------------------------------------
LOCATION...25.0N 70.0W
MAXIMUM SUSTAINED WINDS...50 MPH

WATCHES AND WARNINGS
--------------------
There are no coastal watches or warnings in effect.
"""

        markdown = _nhc_product_markdown(content, product_code='TCP')

        self.assertIsNotNone(markdown)
        assert markdown is not None
        self.assertTrue(markdown.startswith('# Tropical Storm Alpha Advisory Number 1\n'))
        self.assertIn('> ...ALPHA CONTINUES NORTHWEST...', markdown)
        self.assertIn('## SUMMARY OF 1100 AM AST...1500 UTC...INFORMATION', markdown)
        self.assertIn('    LOCATION...25.0N 70.0W', markdown)
        self.assertIn('    MAXIMUM SUSTAINED WINDS...50 MPH', markdown)
        self.assertIn('## WATCHES AND WARNINGS', markdown)
        self.assertIn('There are no coastal watches or warnings in effect.', markdown)
        self.assertNotIn('--------------------', markdown)

    def test_forecast_discussion_markdown_preserves_prose_and_forecast_table(self) -> None:
        content = """\
Tropical Storm Alpha Discussion Number 1
NWS National Hurricane Center Miami FL AL012026
1100 AM AST Fri Aug 14 2026

Alpha is moving northwest and remains over open water.

FORECAST POSITIONS AND MAX WINDS

INIT  14/1500Z 25.0N 70.0W   45 KT  50 MPH
 12H  15/0000Z 26.0N 71.0W   50 KT  60 MPH

$$
Forecaster Example
"""

        markdown = _nhc_product_markdown(content, product_code='TCD')

        self.assertIsNotNone(markdown)
        assert markdown is not None
        self.assertTrue(markdown.startswith('# Tropical Storm Alpha Discussion Number 1\n'))
        self.assertIn('Alpha is moving northwest and remains over open water.', markdown)
        self.assertIn('## FORECAST POSITIONS AND MAX WINDS', markdown)
        self.assertIn('    INIT  14/1500Z 25.0N 70.0W   45 KT  50 MPH', markdown)
        self.assertIn('     12H  15/0000Z 26.0N 71.0W   50 KT  60 MPH', markdown)
        self.assertIn('$$\nForecaster Example', markdown)

    def test_unrecognized_advisory_layout_declines_structured_formatting(self) -> None:
        self.assertIsNone(
            _nhc_product_markdown(
                'Unrecognized provider layout with official prose.',
                product_code='TCP',
            )
        )

    def test_plain_text_markdown_escapes_syntax_and_preserves_lines(self) -> None:
        self.assertEqual(
            plain_text_to_markdown('# Official heading\n* official detail & <tag>'),
            '\\# Official heading  \n\\* official detail &amp; &lt;tag&gt;',
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
