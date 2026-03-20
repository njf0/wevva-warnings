"""Tests for Meteoalarm Atom feed support."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings.backends.meteoalarm_atom import MeteoAlarmAtomBackend
from wevva_warnings.registry import get_source

METEOALARM_ANDORRA_CAP = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>2.49.0.1.20.0.20260318063323.f0301c79-e416-4de6-9e42-0ed94d1dbbc9</identifier>
  <info>
    <language>en-GB</language>
    <event>Extreme avalanches warning</event>
    <severity>Extreme</severity>
    <headline>Moderate avalanches warning at the North zone</headline>
    <description>Moderate avalanches warning at the North zone</description>
    <instruction>Check the avalanche danger bulletin and weather conditions before departure.</instruction>
    <area>
      <areaDesc>North zone</areaDesc>
      <polygon>42.56934,1.44042 42.58703,1.42532 42.59411,1.43768 42.60422,1.43836 42.60523,1.45622 42.61433,1.47682 42.63353,1.46583 42.64312,1.47476 42.65423,1.47682 42.65625,1.48986 42.64969,1.49810 42.64817,1.51390 42.65575,1.55029 42.64464,1.57913 42.62898,1.59698 42.63201,1.63543 42.62746,1.64710 42.62191,1.66290 42.62797,1.68899 42.61736,1.70753 42.61988,1.73294 42.59108,1.72264 42.59007,1.74049 42.58299,1.76315 42.58552,1.77757 42.57642,1.78443 42.56529,1.76658 42.56377,1.75079 42.55315,1.73774 42.53696,1.73362 42.50533,1.72538 42.49065,1.70616 42.49825,1.69036 42.49723,1.66976 42.50693,1.65622 42.52289,1.66228 42.52565,1.64785 42.53693,1.65709 42.53842,1.63515 42.53884,1.61205 42.55565,1.62302 42.55820,1.57365 42.57967,1.58231 42.57223,1.51822 42.55884,1.47348 42.56934,1.44042</polygon>
    </area>
  </info>
</alert>
"""


def _meteoalarm_feed(link_url: str) -> str:
    """Return a minimal Meteoalarm Atom feed.

    Parameters
    ----------
    link_url : str
        CAP document URL to include in the feed.

    Returns
    -------
    str
        Atom feed content with one linked CAP document.

    """
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Meteoalarm</title>
  <entry>
    <title>Example warning</title>
    <link type="application/cap+xml" href="{link_url}" />
  </entry>
</feed>
"""


class MeteoAlarmAtomBackendTests(unittest.TestCase):
    def test_fetch_alerts_follows_linked_cap_documents(self) -> None:
        backend = MeteoAlarmAtomBackend()
        source = get_source('meteoalarm_atom_andorra')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: _meteoalarm_feed(
                    'https://feeds.meteoalarm.org/api/v1/warnings/feeds-andorra/demo-warning'
                ),
                'https://feeds.meteoalarm.org/api/v1/warnings/feeds-andorra/demo-warning': METEOALARM_ANDORRA_CAP,
            }
            return documents[url]

        with patch('wevva_warnings.backends.meteoalarm_atom.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].source, 'meteoalarm_atom_andorra')
        self.assertEqual(alerts[0].headline, 'Moderate avalanches warning at the North zone')
        self.assertEqual(alerts[0].url, 'https://feeds.meteoalarm.org/api/v1/warnings/feeds-andorra/demo-warning')
