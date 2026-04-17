"""Provider backend for MET Norway CAP feeds."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

from ..geometry import point_in_geometry
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


class METNorwayBackend(WarningBackend):
    """Fetch alerts from MET Norway weather alert feeds."""

    backend_id = 'met_no'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a MET Norway CAP source.

        Parameters
        ----------
        source : WarningSource
            Source definition to query.
        lat : float | None, optional
            Latitude used to prefilter feed entries when feed geometry is
            available.
        lon : float | None, optional
            Longitude used to prefilter feed entries when feed geometry is
            available.
        lang : str | None, optional
            Preferred language code used when selecting CAP ``info`` blocks.
        debug : bool, optional
            If True, emit progress information while fetching alerts.

        Returns
        -------
        list[Alert]
            Alerts parsed from linked MET Norway CAP documents.

        """
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        return fetch_cap_documents(
            source,
            _met_no_alert_urls(root, base_url=source.url, lat=lat, lon=lon),
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _met_no_alert_urls(
    root: ElementTree.Element,
    *,
    base_url: str,
    lat: float | None = None,
    lon: float | None = None,
) -> list[str]:
    """Return candidate CAP URLs from a MET Norway RSS feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the MET Norway RSS feed.
    base_url : str
        Base URL used to resolve relative links.
    lat : float | None, optional
        Latitude used for optional prefiltering against feed polygons.
    lon : float | None, optional
        Longitude used for optional prefiltering against feed polygons.

    Returns
    -------
    list[str]
        Linked CAP document URLs discovered in the feed.

    """
    urls: list[str] = []
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue

        geometry = _feed_geometry(item)
        if lat is not None and lon is not None and geometry is not None and not point_in_geometry(lat, lon, geometry):
            continue

        url = absolute_url(base_url, child_text(item, 'link'))
        if url and 'cap=' in url:
            urls.append(url)
    return urls


def _feed_geometry(item: ElementTree.Element) -> dict[str, Any] | None:
    """Return GeoJSON geometry parsed from MET Norway GeoRSS polygons.

    Parameters
    ----------
    item : ElementTree.Element
        RSS item element to inspect.

    Returns
    -------
    dict[str, Any] | None
        Polygon or MultiPolygon geometry if the item contains GeoRSS polygons,
        otherwise ``None``.

    """
    rings = [
        ring
        for child in item
        if local_name(child.tag) == 'polygon'
        if (ring := _parse_georss_polygon((child.text or '').strip()))
    ]
    if not rings:
        return None
    if len(rings) == 1:
        return {'type': 'Polygon', 'coordinates': [rings[0]]}
    return {'type': 'MultiPolygon', 'coordinates': [[ring] for ring in rings]}


def _parse_georss_polygon(text: str) -> list[list[float]] | None:
    """Parse one GeoRSS polygon string into a GeoJSON-style ring.

    Parameters
    ----------
    text : str
        GeoRSS polygon text containing space-separated ``lat lon`` pairs.

    Returns
    -------
    list[list[float]] | None
        Closed GeoJSON-style ring in ``lon, lat`` order, or ``None`` if the
        text cannot be parsed into a valid polygon.

    """
    if not text:
        return None
    parts = text.split()
    if len(parts) < 6 or len(parts) % 2 != 0:
        return None

    ring: list[list[float]] = []
    for index in range(0, len(parts), 2):
        try:
            lat = float(parts[index])
            lon = float(parts[index + 1])
        except ValueError:
            return None
        ring.append([lon, lat])

    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring
